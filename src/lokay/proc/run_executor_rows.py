"""Nest the authored executor_rows child. No Python loop."""

from __future__ import annotations

import argparse

from lokay.graph_run import run_path
from lokay.proc.seed_issue_queue import seed as seed_queue


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
    out = run_path(
        path_id="executor_rows",
        repo="local/executor-rows",
        config_path=config_path,
        live=live,
        extra_inputs={
            "pass_dir": pass_dir,
            "listed": listed,
            "last": last,
            "budget": cap,
        },
    )
    inner = out.get("result") if isinstance(out.get("result"), dict) else out
    result = dict(inner or {})
    return {
        "ok": True,
        "route": str(out.get("route") or result.get("stop") or "idle"),
        "department": "executor",
        "result": {
            **result,
            "department": "executor",
        },
    }
