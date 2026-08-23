"""Bounded append-only history of compact factory-pass receipts."""

from __future__ import annotations

import fcntl
import json
from pathlib import Path
from typing import Any

HISTORY_NAME = "pass-history.jsonl"
DEFAULT_LIMIT = 500


def history_path_for(state_path: Path) -> Path:
    return Path(state_path).expanduser().resolve().parent / HISTORY_NAME


def append_pass_receipt(receipt: dict[str, Any], *, state_path: Path, limit: int = DEFAULT_LIMIT) -> Path:
    """Append one receipt under a file lock and retain the newest ``limit`` rows."""
    target = history_path_for(state_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target.with_suffix(target.suffix + ".lock")
    line = json.dumps(receipt, ensure_ascii=False, default=str)
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        rows = target.read_text(encoding="utf-8", errors="ignore").splitlines() if target.is_file() else []
        rows.append(line)
        keep = rows[-max(1, int(limit)):]
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text("\n".join(keep) + "\n", encoding="utf-8")
        tmp.replace(target)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return target


def read_pass_history(*, state_path: Path, limit: int = 50) -> list[dict[str, Any]]:
    target = history_path_for(state_path)
    if not target.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8", errors="ignore").splitlines()[-max(0, int(limit)):]:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return list(reversed(rows))
