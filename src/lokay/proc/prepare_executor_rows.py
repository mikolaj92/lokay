"""Seed executor leftover, serial launch budget, and the durable resume cursor."""

from __future__ import annotations

import json
from pathlib import Path

from lokay.proc.issue_delivery_occupancy import live_issue_to_pr_receipts
from lokay.proc.run_executor_rows import budget_of
from lokay.proc.seed_issue_queue import seed as seed_queue


CURSOR = "executor-rows.json"


def cursor_path(pass_dir: str) -> Path:
    return Path(pass_dir) / CURSOR


def read_cursor(pass_dir: str) -> dict:
    path = cursor_path(pass_dir)
    if not pass_dir or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_cursor(pass_dir: str, payload: dict) -> None:
    if not pass_dir:
        return
    path = cursor_path(pass_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare(
    *,
    listed: dict,
    last: dict | None,
    pass_dir: str,
    config_path: str | None,
    live: bool,
    budget: int | None = None,
    slot_count: int,
) -> dict:
    last = seed_queue(last)
    cursor = read_cursor(pass_dir)
    if cursor.get("last"):
        last = cursor["last"]
    cap = budget_of(config_path=config_path, live=live, budget=budget)
    spent = max(
        int(cursor.get("spent") or 0),
        len(live_issue_to_pr_receipts()) if live else 0,
    )
    remaining = max(0, cap - spent)
    if cap > int(slot_count):
        return {
            "ok": False,
            "error": "executor budget exceeds authored slots",
            "budget": cap,
            "slot_count": int(slot_count),
        }
    last = last if isinstance(last, dict) else {}
    # Cap/occupancy may make every slot empty so select_next_issue never runs.
    # Still walk listed leftover for the receipt (#1071 / extend #1067).
    from lokay.proc.select_next_issue import select as select_issue

    fuel = select_issue(listed if isinstance(listed, dict) else {}, last)
    leftover_issues = [
        dict(row)
        for row in list(fuel.get("leftover_issues") or [])
        if isinstance(row, dict)
    ]
    # Selected ready row is also fuel when launch budget is already spent.
    if remaining == 0 and str(fuel.get("route") or "") in {"ready", "issue"}:
        head = {
            key: fuel.get(key)
            for key in ("repo", "issue", "title", "labels", "assignees")
            if fuel.get(key) is not None
        }
        if head.get("repo") is not None and head.get("issue") is not None:
            leftover_issues = [head, *leftover_issues]
    out = {
        "ok": True,
        "route": "run",
        "listed": listed,
        "last": last,
        "pass_dir": pass_dir,
        "budget": remaining,
        "cap": cap,
        "slot_count": int(slot_count),
        "spent": spent,
        "live": live,
        "config_path": config_path or "",
        "leftover": len(leftover_issues)
        if leftover_issues
        else int(fuel.get("leftover") or last.get("leftover") or 0),
    }
    if leftover_issues:
        out["leftover_issues"] = leftover_issues
    elif "leftover_issues" in fuel:
        # Explicit empty from select (picked last row): keep the key only when
        # select emitted it; occupied/none omits the key for record_pass (#1067).
        out["leftover_issues"] = []
    return out
