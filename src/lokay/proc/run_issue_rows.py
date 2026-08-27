"""Nest issue_row until leftover is empty or the implement budget is spent."""

from __future__ import annotations

import argparse
import os

from lokay.proc.classify_issue_row import classify, launched_of
from lokay.proc.run_issue_row import run as one_row


def seed_queue(last: dict | None) -> dict:
    if isinstance(last, dict) and last:
        return last
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return {}
    from lokay.pass_receipt import read_pass_receipt

    receipt = read_pass_receipt() or {}
    rem = receipt.get("remaining")
    return rem if isinstance(rem, dict) else {}


def budget_of(*, config_path: str | None, live: bool, budget: int | None) -> int:
    if budget is not None:
        return max(0, int(budget))
    from lokay.proc._common import load_cfg

    cfg = load_cfg(argparse.Namespace(config=config_path))
    return int(cfg.max_issue_to_pr_per_pass) if live else 0


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
    spent = 0
    rows: list[dict] = []
    result: dict = {"route": "none", "leftover": 0, "leftover_issues": []}
    decision = {"ok": True, "route": "idle"}
    while True:
        row = one_row(
            listed=listed,
            last=last,
            config_path=config_path,
            live=live,
            pass_dir=pass_dir,
        )
        rows.append(row)
        if launched_of(row):
            spent += 1
        decision = classify(row, spent=spent, budget=cap)
        inner = row.get("result") if isinstance(row.get("result"), dict) else row
        result = dict(inner or {})
        if decision.get("route") != "continue":
            break
        last = result
    launched = "started" if any(launched_of(row) for row in rows) else result.get("launched")
    leftover = int(decision.get("leftover") or result.get("leftover") or 0)
    leftover_issues = list(decision.get("leftover_issues") or result.get("leftover_issues") or [])
    return {
        "ok": True,
        "route": str(decision.get("route") or "idle"),
        "result": {
            **result,
            "launched": launched,
            "leftover": leftover,
            "leftover_issues": leftover_issues,
            "rows": len(rows),
            "spent": spent,
            "stop": decision.get("route"),
        },
    }
