"""Persistent 4-of-5 confirmation for repeated product-mill failures."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_WINDOW = 5
_QUORUM = 4
_VOLATILE = re.compile(r"(?i)(?:0x)?[0-9a-f]{8,}|\b\d+\b")
_SPACE = re.compile(r"\s+")
# Honest wait / repair limbo must not confirm as mill failure for recovery.
_NON_FAILURE_HEALTH = frozenset(
    {"waiting", "repairing", "idle", "progress", "offline", "overlap"}
)


def history_path_for(state_path: Path) -> Path:
    return state_path.with_name("recovery-history.json")


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in {"error", "message", "reason", "stderr", "stderr_tail"}:
                yield from _strings(item)
            elif isinstance(item, (dict, list)):
                yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def normalize_failure(text: str) -> str:
    value = _SPACE.sub(" ", text).strip().lower()
    value = _VOLATILE.sub("<n>", value)
    return value[:1000]


def _delivered(row: dict[str, Any]) -> bool:
    if row.get("ok") is not True:
        return False
    terminal = row.get("terminal")
    if not isinstance(terminal, dict):
        return False
    if row.get("kind") == "issue_to_pr":
        created = terminal.get("pr_create")
        return isinstance(created, dict) and isinstance(created.get("pr"), dict)
    if row.get("kind") == "pr_triage":
        merged = terminal.get("pr_merge")
        return isinstance(merged, dict) and merged.get("merged") is True
    return False


def observe_run(*, state_path: Path, state_offset: int, mill: dict[str, Any]) -> dict[str, Any]:
    """Describe one run using only events appended while that run held mill.lock."""
    events: list[dict[str, Any]] = []
    try:
        with state_path.open("r", encoding="utf-8") as handle:
            handle.seek(state_offset)
            for line in handle:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    events.append(row)
    except OSError:
        pass

    delivered = any(_delivered(row) for row in events)
    failures: list[str] = []
    evidence: dict[str, str] = {}
    for row in events:
        if row.get("ok") is not False:
            continue
        for raw in _strings(row):
            normalized = normalize_failure(raw)
            if not normalized:
                continue
            fingerprint = hashlib.sha256(normalized.encode()).hexdigest()[:16]
            failures.append(fingerprint)
            evidence.setdefault(fingerprint, raw[:4000])
    mill_health = str(mill.get("health") or "")
    # Waiting/repairing/review limbo are honest non-error outcomes — do not mint a
    # systemic stall fingerprint from the mill envelope alone.
    if (
        not failures
        and not mill.get("ok")
        and mill_health not in _NON_FAILURE_HEALTH
    ):
        raw = str(mill.get("error") or mill.get("health") or "mill failed")
        normalized = normalize_failure(raw)
        fingerprint = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        failures.append(fingerprint)
        evidence[fingerprint] = raw
    dominant = Counter(failures).most_common(1)[0][0] if failures else None
    # A run that delivered a PR or merge is not evidence of a systemic stall.
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "fingerprint": None if delivered else dominant,
        "evidence": "" if delivered or dominant is None else evidence[dominant],
        "delivered": delivered,
        "health": mill.get("health"),
        "progress": int(mill.get("progress") or 0),
    }


def record_observation(path: Path, observation: dict[str, Any]) -> dict[str, Any] | None:
    """Append an observation and return a confirmed signal at 4 matching of 5."""
    rows: list[dict[str, Any]] = []
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, list):
            rows = [row for row in loaded if isinstance(row, dict)]
    except (OSError, ValueError):
        pass
    rows = [*rows, observation][-_WINDOW:]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    tmp.replace(path)

    fingerprint = observation.get("fingerprint")
    if not fingerprint:
        return None
    matches = [row for row in rows if row.get("fingerprint") == fingerprint]
    if len(rows) < _WINDOW or len(matches) < _QUORUM:
        return None
    evidence = next((str(row.get("evidence") or "") for row in reversed(matches)), "")
    return {
        "fingerprint": fingerprint,
        "matches": len(matches),
        "window": len(rows),
        "evidence": evidence,
        "health": "confirmed_stall",
    }
