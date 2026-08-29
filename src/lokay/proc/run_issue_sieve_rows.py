"""Nest issue_sieve_row until leftover is empty. Never launches issue_to_pr."""

from __future__ import annotations

from lokay.graph_run import run_path
from lokay.proc.classify_issue_row import classify
from lokay.proc.run_issue_rows import seed_queue


def run(
    *,
    listed: dict,
    config_path: str | None,
    live: bool,
    pass_dir: str,
    last: dict | None = None,
) -> dict:
    last = seed_queue(last)
    rows: list[dict] = []
    result: dict = {"route": "none", "leftover": 0, "leftover_issues": []}
    decision = {"ok": True, "route": "idle"}
    while True:
        row = run_path(
            path_id="issue_sieve_row",
            repo="local/issue-sieve-row",
            config_path=config_path,
            live=live,
            extra_inputs={
                "pass_dir": pass_dir,
                "listed": listed,
                "last": last,
            },
        )
        rows.append(row)
        decision = classify(row, spent=0, budget=0)
        inner = row.get("result") if isinstance(row.get("result"), dict) else row
        result = dict(inner or {})
        if decision.get("route") != "continue":
            break
        last = result
    return {
        "ok": True,
        "route": str(decision.get("route") or "idle"),
        "department": "issue_triage",
        "launched": None,
        "result": {
            **result,
            "launched": None,
            "leftover": int(decision.get("leftover") or result.get("leftover") or 0),
            "leftover_issues": list(
                decision.get("leftover_issues") or result.get("leftover_issues") or []
            ),
            "rows": len(rows),
            "stop": decision.get("route"),
        },
    }
