from __future__ import annotations

import json
from pathlib import Path

from lokay.decide import DecisionError, from_wire

QUESTIONS = Path(__file__).parents[2] / "questions"

THRESHOLD = 0.85
NIT = 0.5


def hunks(diff: str) -> list[dict]:
    rows = []
    current = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            if current:
                rows.append(current)
            current = {"plik": line[6:], "linia_od": 1, "linia_do": 1, "body": []}
            continue
        if line.startswith("@@") and current is not None:
            plus = line.split("+", 1)[1].split(" ", 1)[0]
            start, _, count = plus.partition(",")
            current["linia_od"] = int(start)
            current["linia_do"] = int(start) + max(int(count or "1") - 1, 0)
            continue
        if current is not None:
            current["body"].append(line)
    if current:
        rows.append(current)
    return rows


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
        log = ((proc.stdout or "") + (proc.stderr or ""))[-3000:]
        if not did_run(proc):
            retry = execute(argv)
            retry_log = ((retry.stdout or "") + (retry.stderr or ""))[-3000:]
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
