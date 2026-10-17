from __future__ import annotations

from dataclasses import replace
from json import dumps
from math import isfinite

import json
import os
import re
import shlex
from pathlib import Path

from lokay import store

from lokay.effects.decide import DecisionError, from_wire
from lokay.types import CheckResult, Finding, Note, parse_finding, to_dict

QUESTIONS = Path(__file__).parents[2] / "questions"

THRESHOLD = 0.85
HUNK_LIMIT = 1500
NIT = 0.5


def classify_multilens(findings: tuple[Finding | Note, ...], file_lines: int | None = None,
                       repeated: bool = False) -> Finding | None:
    lenses = tuple(sorted({item.lens for item in findings if item.lens}))
    if repeated or len(lenses) < 5:
        return None
    for item in findings:
        if (not isinstance(item, Finding) or not item.plik
                or type(item.linia_od) is not int or type(item.linia_do) is not int
                or item.linia_od < 1 or item.linia_do < item.linia_od
                or item.linia_do - item.linia_od + 1 > 50
                or (file_lines is not None and
                    (item.linia_do > file_lines or item.linia_od == 1 and item.linia_do == file_lines))):
            return None
    first = findings[0]
    if any((item.plik, item.linia_od, item.linia_do) !=
           (first.plik, first.linia_od, first.linia_do) for item in findings):
        return None
    probabilities = []
    for item in findings:
        try:
            p = float((item._raw or {}).get("p", 0))
        except (TypeError, ValueError, OverflowError):
            return None
        if not isfinite(p) or not 0 <= p <= 1:
            return None
        probabilities.append(p)
    p = max(probabilities)
    if p < 0.5:
        return None
    representative = findings[probabilities.index(p)]
    raw = to_dict(representative)
    levels = ("low", "medium", "high", "critical")
    severity = raw.get("severity", "medium")
    level = levels.index(severity) if severity in levels else 1
    raw.update(p=p, severity=levels[min(level + 1, 3)], lenses=list(lenses))
    return replace(representative, lenses=lenses, _raw=raw)


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
                current = rows.setdefault(name, {"path": name, "start": None,
                                                  "end": 1, "added": 0, "deleted": 0, "body": ""})
        elif line.startswith("@@") and current is not None:
            current["body"] = (current["body"] + line + "\n")[:HUNK_LIMIT]
            plus = line.split("+", 1)[1].split(" ", 1)[0]
            start, _, count = plus.partition(",")
            start = int(start)
            end = start + max(int(count or "1") - 1, 0)
            current["start"] = min(current["start"], start) if current["start"] is not None else start
            current["end"] = max(current["end"], end)
        elif current is not None:
            current["body"] = (current["body"] + line + "\n")[:HUNK_LIMIT]
            if line.startswith("+"):
                current["added"] += 1
            elif line.startswith("-"):
                current["deleted"] += 1
    return [{"plik": row["path"], "linia_od": row["start"] if row["start"] is not None else 1,
             "linia_do": row["end"], "added": row["added"], "deleted": row["deleted"], "body": row["body"]}
            for row in rows.values()]


def docs_only(diff: str) -> bool:
    paths = []
    for line in diff.splitlines():
        if not line.startswith("diff --git "):
            continue
        try:
            tokens = shlex.split(line)
        except ValueError:
            return False
        if (len(tokens) != 4 or tokens[:2] != ["diff", "--git"]
                or not tokens[2].startswith("a/") or not tokens[3].startswith("b/")):
            return False
        paths.extend(token[2:] for token in tokens[2:])
    return bool(paths) and all(
        path and not Path(path).is_absolute() and ".." not in Path(path).parts
        and (path.startswith("docs/") or Path(path).suffix in {".md", ".rst", ".txt"})
        for path in paths
    )


def lens(kind: str) -> str:
    path = QUESTIONS / f"check_{kind}.json"
    return json.loads(path.read_text())["question"]


def hunk_finding(raw: dict) -> Finding:
    item = parse_finding(raw)
    if not isinstance(item, Finding):
        raise ValueError("hunk has no file")
    return item


def questions(kind: str, rows: list[dict]) -> dict:
    text = " ".join(lens(part) for part in kind.split())
    items = [{
        "id": "next",
        "type": "choice",
        "instructions": text,
        "options": {"ok": "no real bug", "issue": "real bug"},
    }]
    for index, raw in enumerate(rows, start=1):
        row = hunk_finding(raw)
        items.append({
            "id": f"h{index}",
            "type": "bool",
            "instructions": f"{text} {row.plik}:{row.linia_od}-{row.linia_do}",
            "options": {"true": "problem", "false": "fine"},
        })
    return {"state": {}, "questions": items}


def decide_hunks(kind: str, rows: list[dict], wire: dict, model: str) -> dict:
    internal = questions(kind, rows)
    answers = from_wire("tensorfold", model, wire, internal)
    uwagi = []
    nits = []
    for index, raw in enumerate(rows, start=1):
        row = hunk_finding(raw)
        p = answers[f"h{index}"]["probabilities"]["true"]
        item = {"plik": row.plik, "linia_od": row.linia_od, "linia_do": row.linia_do, "pytanie": kind, "p": p}
        if p >= THRESHOLD:
            uwagi.append(item)
        elif p >= NIT:
            nits.append(item)
    choice = answers["next"]["choice"]
    nxt = "issue" if uwagi or choice == "issue" else "ok"
    return {"next": nxt, "confidence": answers["next"]["confidence"], "uwagi": uwagi, "nits": nits,
            "probabilities": {name: answer["probabilities"] for name, answer in answers.items()}}


def check_state(directory: Path, round: int, diff: str, stat: str, ci: dict, **state) -> dict:
    store.ensure_directory(directory)
    patch = directory / f"check-{round}-diff.patch"
    log = directory / f"check-{round}-test.log"
    store.write_artifact(patch, diff)
    store.write_artifact(log, ci["log"])
    return {**state, "diff_stat": stat[:1500], "diff_path": str(patch),
            "test_log_path": str(log), "test_result": ci["result"],
            "tested": ci.get("tested", False), "ci": ci.get("ci"),
            "failures": [{**item, "log": item.get("log", "")[
                -3000 if item.get("warstwa") == "GitHub CI" else -800:]}
                         for item in ci.get("failed") or []]}


def decide_batches(kind: str, rows: list[dict], state: dict, decide_request=None) -> dict:
    from lokay.effects.decide import decide

    decide_request = decide_request or decide
    api = os.environ.get("LOKAY2_DECISION_API") or "mini"
    model = "" if api == "mini" else os.environ.get("LOKAY2_DECISION_MODEL") or os.environ["LOKAY2_MODEL"]

    def request(batch):
        internal = questions(kind, batch)
        internal["state"] = {**state,
                             "issue_title": (state.get("issue_title") or "")[:4000],
                             "issue_body": (state.get("issue_body") or "")[:4000],
                             "kind": kind, "hunks": {
            f"{row.plik}:{row.linia_od}-{row.linia_do}": raw.get("body", "")
            for raw in batch for row in [hunk_finding(raw)]}}
        return internal

    results = []
    reasons = {}
    for batch, answers in _decision_batches(rows, request, decide_request, api, model):
        result = decide_hunks(kind, batch, {
            "model": model, "usage": {"completion_tokens": 0}, "answers": answers,
        }, model)
        for index, row in enumerate(batch, start=1):
            reasons[hunk_finding(row).plik] = "\n".join(reason for reason in (
                answers["next"].get("reason"), answers[f"h{index}"].get("reason")
            ) if reason)
        for finding in result["uwagi"] + result["nits"]:
            parsed = parse_finding(finding)
            if isinstance(parsed, Finding) and reasons[parsed.plik]:
                finding["uzasadnienie"] = reasons[parsed.plik]
        results.append(result)
    result = {"next": "issue" if any(item["next"] == "issue" for item in results) else "ok",
              "confidence": min(item["confidence"] for item in results),
              "uwagi": [row for item in results for row in item["uwagi"]],
              "nits": [row for item in results for row in item["nits"]],
              "probabilities": [item["probabilities"] for item in results]}
    if result["next"] == "issue" and not result["uwagi"]:
        kinds = ("logic bug", "missing handling/validation", "wrong scope (unrelated change)",
                 "security", "docs/plan only instead of code", "other")

        def followup(batch):
            options = {f"{row.plik}:{row.linia_od}-{row.linia_do}": row.plik
                       for row in map(hunk_finding, batch)}
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
            raw_answers = answers
            answers = from_wire("tensorfold", model, {"answers": answers}, followup(batch))
            for qid, answer in answers.items():
                if "reason" in raw_answers[qid]:
                    answer["reason"] = raw_answers[qid]["reason"]
            chosen = answers["where"]["choice"]
            probabilities = answers["where"]["probabilities"]
            p = probabilities[chosen]
            none = probabilities["none"]
            top = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)[:3]
            change = answers["change"]["choice"]
            if state.get("repo") and state.get("issue") is not None:
                from lokay.store import rounds_append

                rounds_append(state["repo"], state["issue"],
                              f"Check follow-up {kind}: chosen={chosen}, p={p}, none={none}, "
                              f"top-3={dumps(top)}, change={change}, "
                              f"change_p={answers['change']['probabilities'][change]}")
            if (chosen != "none" and p == max(probabilities.values())
                    and p >= 2 * none):
                row = next(row for row in map(hunk_finding, batch)
                           if f"{row.plik}:{row.linia_od}-{row.linia_do}" == chosen)
                result["uwagi"].append({"plik": row.plik, "linia_od": row.linia_od, "linia_do": row.linia_do})
                result["uwagi"][-1].update(pytanie=kind, p=p, zmiana=answers["change"]["choice"])
                reason = "\n".join(reason for reason in (
                    reasons.get(row.plik), answers["where"].get("reason"),
                    answers["change"].get("reason")
                ) if reason)
                if reason:
                    result["uwagi"][-1]["uzasadnienie"] = reason
        if not result["uwagi"]:
            result["replan"] = [{"pytanie": kind, "pliki": [hunk_finding(row).plik for row in rows],
                                 "prompt": f"lens {kind} widzi problem w "
                                           + ", ".join(hunk_finding(row).plik for row in rows)
                                           + ", wskaż konkret"}]
    return result


def _decision_batches(rows, request, decide_request, api, model):
    from lokay.effects.decide import _trim_wire, to_wire

    limit = 60000 if api == "chat" else 5500

    def review_wire(internal):
        wire = to_wire(api, model, internal)
        return json.loads(wire["messages"][1]["content"]) if api == "chat" else wire

    batches = []
    batch = []
    for row in rows:
        candidate = batch + [row]
        try:
            internal = request(candidate)
            wire = review_wire(internal)
            fits = (len(dumps(wire)) < limit
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
        wire = _trim_wire(review_wire(internal), limit=limit,
                          string_limit=limit if api == "chat" else 3000)
        internal["state"] = wire.get("state", wire.get("input"))
        wire_questions = wire["questions"]
        for question, item in zip(internal["questions"],
                                  wire_questions.values() if isinstance(wire_questions, dict) else wire_questions):
            question["instructions"] = item.get("instructions", item.get("question"))
        answers = decide_request(internal)
        yield batch, answers


def test_failures(log: str) -> set[str]:
    log = re.sub(r"\x1b\[[0-9;]*m", "", log)
    identifiers = set(re.findall(r"^(?:FAILED|ERROR)\s+(\S+)", log, re.MULTILINE))
    return identifiers or {line.strip() for line in log.splitlines()
                           if re.search(r"\berror\b|\w+Error:|^E\s|\bFAILED\b", line, re.IGNORECASE)}



def apply_checks(outcome: dict, results: tuple[CheckResult, ...], ci: dict | None = None) -> dict:
    from lokay.checks import verdict

    checked = verdict(results, ci)
    located = []
    unlocated = []
    for finding in outcome.get("uwagi") or []:
        (located if isinstance(parse_finding(finding), Finding) else unlocated).append(finding)
    findings = [to_dict(finding) for result in checked["failed"] for finding in result.findings]
    notes = [*(outcome.get("notes") or []), *(outcome.get("replan") or []), *unlocated,
             *({"warstwa": result.name, "log": result.reason, "status": result.status}
               for result in (*checked["unknown"], *checked["unlocated_fail"]))]
    result = checked["result"]
    if result == "merge":
        result = "fix" if located else "merge"
    return {**outcome, **checked, "result": result, "uwagi": [*located, *findings],
            "notes": notes, "replan": [], "unlocated_findings": unlocated}


def aggregate(sha: str, ci: dict, decisions: list[dict]) -> dict:
    if ci.get("sha") != sha or any(item.get("sha", sha) != sha for item in decisions):
        raise DecisionError("sha mismatch")
    uwagi = list(ci.get("failed") or [])
    for item in decisions:
        uwagi.extend(item.get("uwagi") or [])
    notes = [finding for item in decisions if item.get("next") == "issue" and not item.get("uwagi")
             for finding in (item.get("replan") or [{
                 "pytanie": parse_finding(item).lens or item.get("kind") or "check",
                 "prompt": "Check sees a problem; identify a concrete location."}])]
    fix = bool(uwagi) or ci.get("result") == "red"
    ok = ci.get("result") in ("green", "no_ci") and not uwagi
    return {"result": "fix" if fix else "merge" if ok else "wait", "sha": sha, "uwagi": uwagi,
            "replan": [],
            "notes": [*(ci.get("notes") or []),
                      *(note for item in decisions for note in item.get("notes") or []),
                      *({**item, "pytanie": parse_finding(item).lens, "note": item.get("prompt", "")}
                        for item in notes)]}
