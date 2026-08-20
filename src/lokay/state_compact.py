"""Bound the existing JSONL ledger without creating a second source of truth."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Any

_KEEP = {
    "ts",
    "kind",
    "repo",
    "issue",
    "ok",
    "pr",
    "merged",
    "mergedAt",
    "reason",
    "run_id",
    "started_ts",
}


def _semantic(value: Any, out: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        trace = value.get("semantic")
        if isinstance(trace, dict) and trace.get("kind"):
            out.append(dict(trace))
        for child in value.values():
            _semantic(child, out)
    elif isinstance(value, list):
        for child in value:
            _semantic(child, out)


def compact_event(event: dict[str, Any]) -> dict[str, Any]:
    """Retain recovery/yield facts; discard repeated Fala transcripts."""
    compact = {key: event[key] for key in _KEEP if key in event}
    error = event.get("error")
    if isinstance(error, dict):
        code = error.get("code")
        if code:
            compact["error"] = {"code": str(code)}
    elif isinstance(error, str) and error:
        compact["error"] = error[:500]
    traces: list[dict[str, Any]] = []
    _semantic(event, traces)
    if traces:
        compact["semantic_traces"] = traces
    return compact


def compact_state(path: Path, *, min_bytes: int = 8 * 1024 * 1024) -> dict[str, Any]:
    """Atomically rewrite a large ledger while serializing all Lokay writers."""
    if not path.is_file():
        return {"compacted": False, "reason": "missing", "before_bytes": 0, "after_bytes": 0}
    before = path.stat().st_size
    if before < min_bytes:
        return {"compacted": False, "reason": "below_threshold", "before_bytes": before, "after_bytes": before}
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        before = path.stat().st_size
        fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        rows = 0
        kept = 0
        try:
            with path.open(encoding="utf-8", errors="ignore") as source, os.fdopen(fd, "w", encoding="utf-8") as target:
                for line in source:
                    rows += 1
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(event, dict):
                        continue
                    target.write(json.dumps(compact_event(event), ensure_ascii=False) + "\n")
                    kept += 1
                target.flush()
                os.fsync(target.fileno())
            os.replace(raw_tmp, path)
        finally:
            try:
                os.unlink(raw_tmp)
            except FileNotFoundError:
                pass
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    after = path.stat().st_size
    return {"compacted": True, "rows": rows, "kept": kept, "before_bytes": before, "after_bytes": after}
