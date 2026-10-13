from __future__ import annotations

import json
import os
import re
from pathlib import Path

from lokay.decide import DecisionError, from_wire

QUESTIONS = Path(__file__).parents[2] / "questions"

# Binary per-file questions require 0.85; follow-ups require a winning file
# at least twice as likely as none.
THRESHOLD = 0.85
HUNK_LIMIT = 1500
NIT = 0.5


def hunks(diff: str) -> list[dict]:
    rows = {}
    current = None
    old_file = None
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            current = None
        elif line.startswith("--- a/"):
            old_file = line[6:]
        elif line.startswith("+++ "):
            name = line[6:] if line.startswith("+++ b/") else old_file
            if name is not None:
                current = rows.setdefault(name, {"plik": name, "linia_od": None,
                                                  "linia_do": 1, "added": 0, "deleted": 0, "body": ""})
        elif line.startswith("@@") and current is not None:
            current["body"] = (current["body"] + line + "\n")[:HUNK_LIMIT]
            plus = line.split("+", 1)[1].split(" ", 1)[0]
            start, _, count = plus.partition(",")
            start = int(start)
            end = start + max(int(count or "1") - 1, 0)
            current["linia_od"] = min(current["linia_od"], start) if current["linia_od"] is not None else start
            current["linia_do"] = max(current["linia_do"], end)
        elif current is not None:
            current["body"] = (current["body"] + line + "\n")[:HUNK_LIMIT]
            if line.startswith("+"):
                current["added"] += 1
            elif line.startswith("-"):
                current["deleted"] += 1
    return [{**row, "linia_od": row["linia_od"] if row["linia_od"] is not None else 1}
            for row in rows.values()]


def lens(kind: str) -> str:
    path = QUESTIONS / f"check_{kind}.json"
    return json.loads(path.read_text())["question"]


def questions(kind: str, rows: list[dict]) -> dict:
    text = " ".join(lens(part) for part in kind.split())
    items = [{
        "id": "next",
        "type": "choice",
        "instructions": text,
        "options": {"ok": "no real bug", "issue": "real bug"},
    }]
    for index, row in enumerate(rows, start=1):
        items.append({
            "id": f"h{index}",
            "type": "bool",
            "instructions": f"{text} {row['plik']}:{row['linia_od']}-{row['linia_do']}",
            "options": {"true": "problem", "false": "fine"},
        })
    return {"state": {}, "questions": items}


def decide_hunks(kind: str, rows: list[dict], wire: dict, model: str) -> dict:
    internal = questions(kind, rows)
    answers = from_wire("tensorfold", model, wire, internal)
    uwagi = []
    nits = []
    for index, row in enumerate(rows, start=1):
        p = answers[f"h{index}"]["probabilities"]["true"]
        item = {"plik": row["plik"], "linia_od": row["linia_od"], "linia_do": row["linia_do"], "pytanie": kind, "p": p}
        if p >= THRESHOLD:
            uwagi.append(item)
        elif p >= NIT:
            nits.append(item)
    choice = answers["next"]["choice"]
    nxt = "issue" if uwagi or choice == "issue" else "ok"
    return {"next": nxt, "confidence": answers["next"]["confidence"], "uwagi": uwagi, "nits": nits,
            "probabilities": {name: answer["probabilities"] for name, answer in answers.items()}}


def check_state(directory: Path, round: int, diff: str, stat: str, ci: dict, **state) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    patch = directory / f"check-{round}-diff.patch"
    log = directory / f"check-{round}-test.log"
    patch.write_text(diff)
    log.write_text(ci["log"])
    return {**state, "diff_stat": stat[:1500], "diff_path": str(patch),
            "test_log_path": str(log), "test_result": ci["result"],
            "tested": ci.get("tested", False), "ci": ci.get("ci"),
            "failures": [{**item, "log": item.get("log", "")[-800:]}
                         for item in ci.get("failed") or []]}


def decide_batches(kind: str, rows: list[dict], state: dict, decide_request=None) -> dict:
    from lokay.decide import decide

    decide_request = decide_request or decide
    api = os.environ.get("LOKAY2_DECISION_API") or "mini"
    model = "" if api == "mini" else os.environ.get("LOKAY2_DECISION_MODEL") or os.environ["LOKAY2_MODEL"]

    def request(batch):
        internal = questions(kind, batch)
        internal["state"] = {**state, "kind": kind, "hunks": {
            f"{row['plik']}:{row['linia_od']}-{row['linia_do']}": row.get("body", "")
            for row in batch}}
        return internal

    results = []
    for batch, answers in _decision_batches(rows, request, decide_request, api, model):
        results.append(decide_hunks(kind, batch, {
            "model": model, "usage": {"completion_tokens": 0}, "answers": answers,
        }, model))
    result = {"next": "issue" if any(item["next"] == "issue" for item in results) else "ok",
              "confidence": min(item["confidence"] for item in results),
              "uwagi": [row for item in results for row in item["uwagi"]],
              "nits": [row for item in results for row in item["nits"]],
              "probabilities": [item["probabilities"] for item in results]}
    if result["next"] == "issue" and not result["uwagi"]:
        kinds = ("logic bug", "missing handling/validation", "wrong scope (unrelated change)",
                 "security", "docs/plan only instead of code", "other")

        def followup(batch):
            options = {f"{row['plik']}:{row['linia_od']}-{row['linia_do']}": row['plik'] for row in batch}
            return {"state": request(batch)["state"], "questions": [
                {"id": "where", "type": "choice",
                 "instructions": lens_text + " Where is the problem?",
                 "options": {**options, "none": "no concrete finding"}},
                {"id": "change", "type": "choice",
                 "instructions": "What kind of change is needed?",
                 "options": {name: name for name in kinds}},
            ]}

        lens_text = " ".join(lens(part) for part in kind.split())
        for batch, answers in _decision_batches(rows, followup, decide_request, api, model):
            answers = from_wire("tensorfold", model, {"answers": answers}, followup(batch))
            chosen = answers["where"]["choice"]
            probabilities = answers["where"]["probabilities"]
            p = probabilities[chosen]
            none = probabilities["none"]
            top = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)[:3]
            change = answers["change"]["choice"]
            if state.get("repo") and state.get("issue") is not None:
                from lokay.state import rounds_append

                rounds_append(state["repo"], state["issue"],
                              f"Check follow-up {kind}: chosen={chosen}, p={p}, none={none}, "
                              f"top-3={json.dumps(top)}, change={change}, "
                              f"change_p={answers['change']['probabilities'][change]}")
            if (chosen != "none" and p == max(probabilities.values())
                    and p >= 2 * none):
                row = next(row for row in batch if f"{row['plik']}:{row['linia_od']}-{row['linia_do']}" == chosen)
                result["uwagi"].append({key: row[key] for key in ("plik", "linia_od", "linia_do")})
                result["uwagi"][-1].update(pytanie=kind, p=p, zmiana=answers["change"]["choice"])
        if not result["uwagi"]:
            result["replan"] = [{"pytanie": kind, "pliki": [row["plik"] for row in rows],
                                 "prompt": f"lens {kind} widzi problem w "
                                           + ", ".join(row["plik"] for row in rows)
                                           + ", wskaż konkret"}]
    return result


def _decision_batches(rows, request, decide_request, api, model):
    from lokay.decide import _trim_wire, to_wire

    batches = []
    batch = []
    for row in rows:
        candidate = batch + [row]
        try:
            internal = request(candidate)
            wire = to_wire(api, model, internal)
            fits = (len(json.dumps(wire)) < 5500
                    and wire.get("state", wire.get("input")) == internal["state"])
        except DecisionError:
            fits = False
        if batch and not fits:
            batches.append(batch)
            batch = [row]
        else:
            batch = candidate
    batches.append(batch)
    for batch in batches:
        internal = request(batch)
        # Last resort for a single oversized row or unusually large state.
        wire = _trim_wire(to_wire(api, model, internal), limit=5500)
        internal["state"] = wire.get("state", wire.get("input"))
        wire_questions = wire["questions"]
        for question, item in zip(internal["questions"],
                                  wire_questions.values() if isinstance(wire_questions, dict) else wire_questions):
            question["instructions"] = item.get("instructions", item.get("question"))
        answers = decide_request(internal)
        yield batch, answers


def local_ci(sha: str, tests: list[list[str]], cwd, timeout: int = 600) -> dict:
    from subprocess import CompletedProcess, TimeoutExpired
    from lokay.run import run_process
    from lokay.build import generated_cleanup

    def execute(argv):
        try:
            with generated_cleanup(Path(cwd)):
                return run_process(argv, cwd=cwd, timeout=timeout)
        except (TimeoutExpired, OSError) as exc:
            return CompletedProcess(argv, 1, "", str(exc))

    def did_run(proc):
        log = (proc.stdout or "") + (proc.stderr or "")
        markers = ("collected 0 items", "no tests ran", "error: failed to", "no solution found",
                   "modulenotfounderror", "command not found", "no such file or directory")
        if "LOKAY_TEST_CWD=" in log:
            segments = re.split(r"^LOKAY_TEST_CWD=.+$", log, flags=re.MULTILINE)[1:]
            if not all(did_run(CompletedProcess(proc.args, 0, segment, "")) for segment in segments):
                return False
        summary = re.search(
            r"\b[1-9]\d* passed\b|\bRan [1-9]\d* tests?\b|\bExecuted [1-9]\d* tests?\b"
            r"|\btests? [1-9]\d*\b|\bscenarios: [1-9]\d*/[1-9]\d*; errors=0", log)
        return (proc.returncode == 0 and summary is not None
                and not re.search(r"\b0 passed\b", log)
                and not any(marker in log.lower() for marker in markers))

    failed = []
    notes = []
    logs = []
    tested_cwds = set()
    if not tests:
        notes.append({"warstwa": "tests", "plik": "", "log": "no tests configured"})
    for argv in tests:
        proc = execute(argv)
        log = (proc.stdout or "") + (proc.stderr or "")
        ran = did_run(proc)
        if not ran:
            retry = execute(argv)
            retry_log = (retry.stdout or "") + (retry.stderr or "")
            flaky = did_run(retry)
            ran = flaky
            item = {"warstwa": " ".join(argv), "plik": "", "linia": None,
                    "sha": sha, "flaky": flaky, "log": log + "\nRetry:\n" + retry_log}
            (notes if flaky else failed).append(item)
            log = item["log"]
        if ran:
            directories = re.findall(r"^LOKAY_TEST_CWD=(.+)$", log, re.MULTILINE)
            tested_cwds.update(str(Path(path).resolve()) for path in directories or [cwd])
        logs.append(log)
    return {"result": "red" if failed else "green", "sha": sha,
            "tested": bool(tested_cwds), "tested_cwds": sorted(tested_cwds),
            "failed": failed, "notes": notes, "log": "\n".join(logs)}


def aggregate(sha: str, ci: dict, decisions: list[dict]) -> dict:
    if ci.get("sha") != sha or any(item.get("sha", sha) != sha for item in decisions):
        raise DecisionError("sha mismatch")
    if ci.get("result") in ("pending", "sha_moved"):
        return {"result": "check", "sha": sha, "uwagi": []}
    uwagi = list(ci.get("failed") or [])
    for item in decisions:
        uwagi.extend(item.get("uwagi") or [])
    replan = [finding for item in decisions if item.get("next") == "issue" and not item.get("uwagi")
              for finding in (item.get("replan") or [{"prompt": "Check sees a problem; identify a concrete location."}])]
    ok = ci.get("result") == "green" and not uwagi
    return {"result": "plan" if replan else "merge" if ok else "fix", "sha": sha, "uwagi": uwagi,
            "replan": replan,
            "notes": [*(ci.get("notes") or []),
                      *(note for item in decisions for note in item.get("notes") or [])]}
