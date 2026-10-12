from __future__ import annotations

import json
import os
from pathlib import Path

from lokay.decide import DecisionError, from_wire

QUESTIONS = Path(__file__).parents[2] / "questions"

THRESHOLD = 0.85
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
                                                  "linia_do": 1, "added": 0, "deleted": 0})
        elif line.startswith("@@") and current is not None:
            plus = line.split("+", 1)[1].split(" ", 1)[0]
            start, _, count = plus.partition(",")
            start = int(start)
            end = start + max(int(count or "1") - 1, 0)
            current["linia_od"] = min(current["linia_od"], start) if current["linia_od"] is not None else start
            current["linia_do"] = max(current["linia_do"], end)
        elif current is not None:
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
    return {"next": nxt, "confidence": answers["next"]["confidence"], "uwagi": uwagi, "nits": nits}


def check_state(directory: Path, round: int, diff: str, stat: str, ci: dict, **state) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    patch = directory / f"check-{round}-diff.patch"
    log = directory / f"check-{round}-test.log"
    patch.write_text(diff)
    log.write_text(ci["log"])
    return {**state, "diff_stat": stat[:1500], "diff_path": str(patch),
            "test_log_path": str(log), "test_result": ci["result"],
            "failures": [{**item, "log": item.get("log", "")[-800:]}
                         for item in ci.get("failed") or []]}


def decide_batches(kind: str, rows: list[dict], state: dict, decide_request=None) -> dict:
    from lokay.decide import _trim_wire, decide, to_wire

    decide_request = decide_request or decide
    api = os.environ.get("LOKAY2_DECISION_API") or "mini"
    model = "" if api == "mini" else os.environ.get("LOKAY2_DECISION_MODEL") or os.environ["LOKAY2_MODEL"]

    def request(batch):
        internal = questions(kind, batch)
        internal["state"] = {**state, "files": "\n".join(
            f"{row['plik']} +{row.get('added', 0)} -{row.get('deleted', 0)}" for row in batch)}
        return internal

    batches = []
    batch = []
    for row in rows:
        candidate = batch + [row]
        try:
            fits = len(json.dumps(to_wire(api, model, request(candidate)))) < 5500
        except DecisionError:
            fits = False
        if batch and not fits:
            batches.append(batch)
            batch = [row]
        else:
            batch = candidate
    batches.append(batch)
    results = []
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
        result = decide_hunks(kind, batch, {
            "model": model, "usage": {"completion_tokens": 0},
            "answers": answers,
        }, model)
        results.append(result)
    return {"next": "issue" if any(result["next"] == "issue" for result in results) else "ok",
            "confidence": min(result["confidence"] for result in results),
            "uwagi": [item for result in results for item in result["uwagi"]],
            "nits": [item for result in results for item in result["nits"]]}


def local_ci(sha: str, tests: list[list[str]], cwd, timeout: int = 600) -> dict:
    from subprocess import CompletedProcess, TimeoutExpired
    from lokay.run import run_process

    def execute(argv):
        try:
            return run_process(argv, cwd=cwd, timeout=timeout)
        except (TimeoutExpired, OSError) as exc:
            return CompletedProcess(argv, 1, "", str(exc))

    def did_run(proc):
        log = (proc.stdout or "") + (proc.stderr or "")
        markers = ("collected 0 items", "no tests ran", "error: failed to", "no solution found",
                   "modulenotfounderror", "command not found", "no such file or directory")
        return proc.returncode == 0 and not any(marker in log.lower() for marker in markers)

    failed = []
    notes = []
    logs = []
    if not tests:
        notes.append({"warstwa": "tests", "plik": "", "log": "no tests configured"})
    for argv in tests:
        proc = execute(argv)
        log = (proc.stdout or "") + (proc.stderr or "")
        if not did_run(proc):
            retry = execute(argv)
            retry_log = (retry.stdout or "") + (retry.stderr or "")
            flaky = did_run(retry)
            item = {"warstwa": " ".join(argv), "plik": "", "linia": None,
                    "sha": sha, "flaky": flaky, "log": log + "\nRetry:\n" + retry_log}
            (notes if flaky else failed).append(item)
            log = item["log"]
        logs.append(log)
    return {"result": "red" if failed else "green", "sha": sha,
            "failed": failed, "notes": notes, "log": "\n".join(logs)}


def aggregate(sha: str, ci: dict, decisions: list[dict]) -> dict:
    if ci.get("sha") != sha or any(item.get("sha", sha) != sha for item in decisions):
        raise DecisionError("sha mismatch")
    if ci.get("result") in ("pending", "sha_moved"):
        return {"result": "check", "sha": sha, "uwagi": []}
    uwagi = list(ci.get("failed") or [])
    for item in decisions:
        uwagi.extend(item.get("uwagi") or [])
    ok = ci.get("result") == "green" and all(item.get("next") == "ok" for item in decisions)
    if not ok:
        uwagi.extend(ci.get("notes") or [])
    return {"result": "merge" if ok else "fix", "sha": sha, "uwagi": uwagi,
            "notes": ci.get("notes") or []}
