"""Durable per-PR pr_repair attempt receipts (lifetime K, not per-tick fleet).

``limits.max_repairs_per_tick`` (default 1) is reused as the per-PR lifetime
budget K. After attempts >= budget the receipt parks; select fail-closes so the
next factory tick does not invoke pr_repair again for that PR.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def receipts_dir(
    *, home: Path | str | None = None, state_dir: Path | str | None = None
) -> Path:
    if state_dir is not None:
        return Path(state_dir).expanduser().resolve() / "pr-repair-receipts"
    root = Path(home).expanduser() if home is not None else Path.home()
    return root / ".lokay" / "pr-repair-receipts"


def receipt_path(
    repo: str,
    pr: int,
    *,
    home: Path | str | None = None,
    state_dir: Path | str | None = None,
) -> Path:
    slug = f"{str(repo).replace('/', '__')}__{int(pr)}.json"
    return receipts_dir(home=home, state_dir=state_dir) / slug


def resolve_state_dir(config_path: str | None) -> Path | None:
    if not config_path:
        return None
    try:
        from lokay.config import load_config

        return load_config(config_path).state_path.expanduser().resolve().parent
    except (OSError, ValueError, FileNotFoundError, TypeError):
        return None


def resolve_budget(config_path: str | None) -> int:
    """Per-PR lifetime K; matches config default max_repairs_per_tick=1."""
    if not config_path:
        return 1
    try:
        from lokay.config import load_config

        return max(1, int(load_config(config_path).max_repairs_per_tick))
    except (OSError, ValueError, FileNotFoundError, TypeError):
        return 1


def _empty(repo: str, pr: int, *, budget: int = 1) -> dict[str, Any]:
    return {
        "repo": str(repo),
        "pr": int(pr),
        "attempts": 0,
        "budget": max(1, int(budget)),
        "last_head_sha": "",
        "last_terminal": "",
        "updated_at": "",
        "parked": False,
    }


def read(
    repo: str,
    pr: int,
    *,
    home: Path | str | None = None,
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    path = receipt_path(repo, pr, home=home, state_dir=state_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def stamp(
    repo: str,
    pr: int,
    *,
    attempt_delta: int = 1,
    head_sha: str = "",
    terminal: str = "",
    budget: int = 1,
    home: Path | str | None = None,
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Increment attempts; park when attempts >= budget."""
    budget_n = max(1, int(budget))
    previous = read(repo, pr, home=home, state_dir=state_dir)
    base = _empty(repo, pr, budget=budget_n)
    if previous:
        base.update(previous)
        # Keep an existing budget unless caller raises it explicitly via arg
        # and receipt had none; prefer stamped budget arg as the live K.
        base["budget"] = budget_n
    attempts = max(0, int(base.get("attempts") or 0)) + int(attempt_delta)
    parked = attempts >= budget_n
    payload: dict[str, Any] = {
        "repo": str(repo),
        "pr": int(pr),
        "attempts": attempts,
        "budget": budget_n,
        "last_head_sha": str(head_sha or base.get("last_head_sha") or ""),
        "last_terminal": str(terminal or base.get("last_terminal") or ""),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "parked": parked,
    }
    path = receipt_path(repo, pr, home=home, state_dir=state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        tmp.replace(path)
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        # Still return the logical receipt so callers can park even if disk fails.
    return payload


def clear(
    repo: str,
    pr: int,
    *,
    home: Path | str | None = None,
    state_dir: Path | str | None = None,
) -> bool:
    """Drop receipt when PR is gone (merge/close); optional reset."""
    path = receipt_path(repo, pr, home=home, state_dir=state_dir)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False
