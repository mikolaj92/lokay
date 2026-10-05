"""Seed sieve leftover, budget, and the durable resume cursor."""

from __future__ import annotations

import json
from pathlib import Path

from lokay.proc.run_issue_sieve_rows import budget_of

CURSOR = "issue-sieve.json"


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


def tail_path(config_path: str) -> Path:
    from lokay.config import load_config

    return load_config(config_path).state_path.with_name("issue-sieve-tail.json")


def seed_sieve(last: dict | None, config_path: str | None, listed: dict) -> dict:
    # Executor receipts contain ready-only leftovers, never an inbox cursor.
    if isinstance(last, dict) and last.get("department") == "issue_triage":
        return last
    if config_path:
        try:
            data = json.loads(tail_path(config_path).read_text())
            if isinstance(data, dict) and data.get("leftover_issues"):
                from lokay.proc.walk_issue_leftover import identity

                rows = list(listed.get("issues") or [])
                live = {identity(row) for row in rows}
                kept = [row for row in data["leftover_issues"] if identity(row) in live]
                known = {identity(row) for row in kept}
                fresh = [row for row in rows if identity(row) not in known]
                return {**data, "leftover_issues": kept + fresh}
        except (OSError, ValueError, TypeError, AttributeError):
            pass
    return {}


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
    last = seed_sieve(last, config_path, listed)
    cursor = read_cursor(pass_dir)
    if cursor.get("last"):
        last = cursor["last"]
    cap = budget_of(config_path=config_path, live=live, budget=budget)
    spent = int(cursor.get("spent") or 0)
    remaining = max(0, cap - spent)
    if cap > int(slot_count):
        return {
            "ok": False,
            "error": "issue sieve budget exceeds authored slots",
            "budget": cap,
            "slot_count": int(slot_count),
        }
    return {
        "ok": True,
        "route": "run",
        "listed": listed,
        "last": last if isinstance(last, dict) else {},
        "decisions": list(cursor.get("decisions") or []),
        "pass_dir": pass_dir,
        "budget": remaining,
        "cap": cap,
        "slot_count": int(slot_count),
        "spent": spent,
        "live": live,
        "config_path": config_path or "",
    }
