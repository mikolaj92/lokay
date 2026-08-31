"""Nest issue_sieve_row until leftover is empty or the triage budget is spent.

Never launches issue_to_pr. A bounded sieve must yield to the executor in the
same factory pass instead of starving it on a large catalog.
"""

from __future__ import annotations

import argparse

from lokay.graph_run import run_path
from lokay.proc.classify_issue_row import classify
from lokay.proc.seed_issue_queue import seed as seed_queue


def budget_of(*, config_path: str | None, live: bool, budget: int | None) -> int:
    if budget is not None:
        return max(0, int(budget))
    from lokay.proc._common import load_cfg

    cfg = load_cfg(argparse.Namespace(config=config_path))
    return max(0, int(cfg.max_triage_per_tick)) if live else 0


def run(
    *,
    listed: dict,
    config_path: str | None,
    live: bool,
    pass_dir: str,
    budget: int | None = None,
    last: dict | None = None,
) -> dict:
    last = seed_queue(last)
    cap = budget_of(config_path=config_path, live=live, budget=budget)
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
        decision = classify(row, spent=len(rows), budget=cap, bound_any=True)
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
            "spent": len(rows),
            "budget": cap,
            "stop": decision.get("route"),
        },
    }
