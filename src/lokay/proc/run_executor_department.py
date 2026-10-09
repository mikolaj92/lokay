"""Parent slot: executor_department. Code and PR. Not sieve. Not merge."""

from __future__ import annotations

from lokay.graph_run import run_path
from lokay.sieve_decision import listed_of


def child_graph(
    *,
    pass_dir: str,
    config_path: str | None,
    live: bool,
    triage: dict | None = None,
    listed: dict | None = None,
    last: dict | None = None,
) -> dict:
    return run_path(
        path_id="executor_department",
        repo="local/executor-department",
        config_path=config_path,
        live=live,
        extra_inputs={
            "pass_dir": pass_dir,
            "triage": triage or {},
            "listed": listed or {},
            "last": last or {},
        },
    )


def last_cursor(config_path: str | None) -> dict:
    """Previous pass's executor cursor from last-pass.json; {} keeps the old behaviour."""
    import argparse
    from datetime import datetime, timezone

    from lokay.pass_receipt import read_pass_receipt
    from lokay.proc._common import load_cfg

    try:
        receipt = read_pass_receipt(state_path=load_cfg(argparse.Namespace(config=config_path)).state_path) or {}
        ts = str(receipt.get("ts") or "")
        if ts and (datetime.now(timezone.utc) - datetime.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds() > 7200:
            return {}  # stale receipt: fresh walk
    except Exception:
        return {}
    remaining = receipt.get("remaining")
    if not isinstance(remaining, dict) or not isinstance(remaining.get("leftover_issues"), list):
        return {}
    return {"leftover_issues": remaining["leftover_issues"], "leftover": remaining.get("leftover")}


def run(
    *,
    pass_dir: str,
    config_path: str | None,
    live: bool,
    triage_ran: bool = False,
    triage: dict | None = None,
) -> dict:
    del triage_ran  # sieve is a sibling department; this slot always codes
    from pathlib import Path
    import json

    snapshot = Path(pass_dir) / "listed-issues.json"
    listed = json.loads(snapshot.read_text()) if snapshot.is_file() else listed_of(triage)
    return {
        **child_graph(
            pass_dir=pass_dir,
            config_path=config_path,
            live=live,
            triage=triage,
            listed=listed,
            last=last_cursor(config_path) if live else {},
        ),
        "body": "child",
    }
