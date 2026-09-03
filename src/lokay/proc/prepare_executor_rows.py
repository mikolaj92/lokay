"""Seed executor leftover, serial launch budget, and the durable resume cursor."""

from __future__ import annotations

import json
from pathlib import Path

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
    spent = int(cursor.get("spent") or 0)
    remaining = max(0, cap - spent)
    if cap > int(slot_count):
        return {
            "ok": False,
            "error": "executor budget exceeds authored slots",
            "budget": cap,
            "slot_count": int(slot_count),
        }
    return {
        "ok": True,
        "route": "run",
        "listed": listed,
        "last": last if isinstance(last, dict) else {},
        "pass_dir": pass_dir,
        "budget": remaining,
        "cap": cap,
        "slot_count": int(slot_count),
        "spent": spent,
        "live": live,
        "config_path": config_path or "",
    }
