"""Classify a pass-ceiling stop without erasing progress or resume context."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lokay.work_units import project_work_units, status_work_units


_WAITING = frozenset(
    {
        "checks_pending",
        "waiting",
        "waiting_external",
        "review_limbo",
        "implementing",
        "starting",
    }
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def classify(
    *,
    state_dir: Path,
    elapsed_seconds: float,
    remaining: dict[str, Any] | None = None,
    remaining_source: str | None = None,
) -> dict[str, Any]:
    activity = _read_json(Path(state_dir) / "activity.json")
    units = project_work_units(Path(state_dir) / "state.jsonl")
    visible, latest = status_work_units(units)
    transitions = int(activity.get("transitions") or 0)
    last_path = str(activity.get("path") or "").strip() or None
    last_atom = str(activity.get("atom") or "").strip() or None
    work_id = str(activity.get("work_id") or "").strip() or None
    repo = str(activity.get("repo") or "").strip() or None
    pending = [row for row in visible if not row.get("delivered")]
    waiting = any(
        str(row.get("state") or "") in _WAITING or str(row.get("reason") or "") in _WAITING
        for row in pending
    )
    if transitions > 0 or latest or remaining_source == "inflight_working":
        reason = "ceiling_with_progress"
    elif waiting:
        reason = "ceiling_waiting_external"
    else:
        reason = "ceiling_stalled"
    payload: dict[str, Any] = {
        "ok": False,
        "health": "pass_ceiling",
        "reason": reason,
        "elapsed_seconds": float(elapsed_seconds),
        "transitions": transitions,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if last_path:
        payload["last_path"] = last_path
        payload["resume_from"] = last_path
    if last_atom:
        payload["last_atom"] = last_atom
    if work_id:
        payload["work_id"] = work_id
    if repo:
        payload["repo"] = repo
    if remaining is not None:
        payload["remaining"] = remaining
    if remaining_source:
        payload["remaining_source"] = remaining_source
    if latest:
        payload["latest_delivery"] = latest
    if visible:
        payload["work_units"] = visible
    return payload
