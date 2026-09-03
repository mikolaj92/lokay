"""Nest the authored issue_sieve_rows child. No Python loop."""

from __future__ import annotations

import argparse

from lokay.graph_run import run_path
from lokay.proc._common import load_cfg
from lokay.proc.seed_issue_queue import seed as seed_queue


def budget_of(*, config_path: str | None, live: bool, budget: int | None) -> int:
    if budget is not None:
        return max(0, int(budget))
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
    extra = {
        "pass_dir": pass_dir,
        "listed": listed,
        "last": last,
        "budget": cap,
    }
    out = run_path(
        path_id="issue_sieve_rows",
        repo="local/issue-sieve-rows",
        config_path=config_path,
        live=live,
        extra_inputs=extra,
    )
    inner = out.get("result") if isinstance(out.get("result"), dict) else out
    result = dict(inner or {})
    return {
        "ok": True,
        "route": str(out.get("route") or result.get("stop") or "idle"),
        "department": "issue_triage",
        "launched": None,
        "result": {
            **result,
            "launched": None,
            "department": "issue_triage",
            "budget": cap,
        },
    }
