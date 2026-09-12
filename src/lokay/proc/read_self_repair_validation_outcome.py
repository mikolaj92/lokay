"""Read the last completed validation outcome for one candidate HEAD."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

_TIMED_OUT = '"test_timed_out"'
_INCOMPLETE = frozenset({"running", "ready", "created", "pending", "leased"})


def _load(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _values(payload: dict[str, Any]) -> dict[str, Any]:
    nested = payload.get("payload")
    if isinstance(nested, dict):
        payload = nested
    values = payload.get("values")
    return values if isinstance(values, dict) else payload


def _head_of(payload: dict[str, Any]) -> str:
    values = _values(payload)
    return str(
        values.get("head")
        or values.get("commit")
        or values.get("expected_commit")
        or values.get("validated_commit")
        or payload.get("expected_commit")
        or ""
    )


def _sha_matches(stored: str, head: str) -> bool:
    if not stored:
        return False
    if stored == head:
        return True
    if "<redacted>" not in stored:
        return False
    prefix, _, suffix = stored.partition("<redacted>")
    return head.startswith(prefix) and (not suffix or head.endswith(suffix))


def _timed_out(payload: dict[str, Any], raw: str | None) -> bool:
    values = _values(payload)
    if values.get("test_timed_out") is True:
        return True
    blob = " ".join(
        part
        for part in (str(payload.get("message") or ""), raw or "")
        if part
    )
    if '"test_timed_out"' not in blob:
        return False
    return "true" in blob[blob.find('"test_timed_out"'):blob.find('"test_timed_out"') + 40]


def read_for_head(candidate: dict) -> dict[str, Any]:
    """Return stored validation facts for this HEAD, or empty if unknown.

    The prepare graph must not resume a SHA that already timed out. Missing
    evidence stays empty so a first attempt can still validate. Adapter
    failures keep the timeout in error_json and may redact the SHA. A still
    running attempt is not evidence.
    """
    head = str(candidate.get("head") or candidate.get("candidate_commit") or "")
    if not head:
        return {}
    home = Path(str(candidate.get("journal_home") or "")).expanduser()
    if not str(candidate.get("journal_home") or "").strip():
        home = Path.home() / ".lokay" / "fala"
    db = home / "self_repair_validate" / "state.sqlite"
    if not db.is_file():
        return {}
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            names = {
                str(row[1])
                for row in conn.execute("PRAGMA table_info(processes)").fetchall()
            }
            fields = [
                name
                for name in ("status", "input_json", "output_json", "error_json")
                if name in names
            ]
            if "output_json" not in fields and "error_json" not in fields:
                return {}
            times = [name for name in ("finished_at", "started_at", "created_at") if name in names]
            order = " ORDER BY " + ", ".join(f"{name} DESC" for name in times) if times else ""
            select = ", ".join(fields)
            rows = conn.execute(
                f"SELECT {select} FROM processes "
                "WHERE id LIKE '%run_self_repair_tests'" + order
            ).fetchall()
    except sqlite3.Error:
        return {}
    for row in rows:
        record = dict(zip(fields, row))
        if str(record.get("status") or "").lower() in _INCOMPLETE:
            continue
        identity = _load(record.get("input_json"))
        result = _load(record.get("output_json"))
        error = _load(record.get("error_json"))
        stored = _head_of(result) or _head_of(identity) or _head_of(error)
        if not _sha_matches(stored, head):
            continue
        if _timed_out(result, record.get("output_json")) or _timed_out(
            error, record.get("error_json")
        ):
            return {"head": head, "test_timed_out": True, "ok": False}
        return _values(result) or _values(error)
    return {}
