"""Write a small live-mill activity checkpoint beside state.jsonl.

Ceiling receipts read this file for resume_from / last_atom / transitions.
Status stays read-only. A failed write must not abort the atom.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ACTIVITY_NAME = "activity.json"


def _state_dir(inputs: dict[str, Any]) -> Path | None:
    config_path = str(inputs.get("config_path") or os.environ.get("LOKAY_CONFIG") or "")
    if config_path:
        try:
            from lokay.config import load_config

            return load_config(config_path).state_path.parent
        except (OSError, ValueError, FileNotFoundError, TypeError):
            return None
    return None


def _work_id(inputs: dict[str, Any]) -> str | None:
    repo = str(inputs.get("repo") or "").strip()
    issue = inputs.get("issue")
    if issue is None:
        issue = inputs.get("issue_number")
    try:
        number = int(issue)
    except (TypeError, ValueError):
        number = 0
    if repo and "/" in repo and number > 0:
        return f"{repo}#{number}"
    work_id = str(inputs.get("work_id") or "").strip()
    return work_id or None


def _path_id(process_id: str | None, inputs: dict[str, Any]) -> str | None:
    explicit = str(inputs.get("path_id") or "").strip()
    if explicit:
        return explicit
    raw = str(process_id or "").strip()
    if not raw:
        return None
    if ":" in raw:
        return raw.split(":", 1)[0] or None
    if "/" in raw:
        return raw.split("/", 1)[0] or None
    return raw or None


def record_atom_start(
    *,
    atom: str,
    inputs: dict[str, Any] | None = None,
    process_id: str | None = None,
) -> dict[str, Any] | None:
    """Update activity.json for this atom. Never raises."""
    payload_inputs = inputs if isinstance(inputs, dict) else {}
    try:
        state_dir = _state_dir(payload_inputs)
        if state_dir is None:
            return None
        path = state_dir / ACTIVITY_NAME
        previous: dict[str, Any] = {}
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                previous = loaded
        except (OSError, ValueError, json.JSONDecodeError):
            previous = {}
        try:
            transitions = int(previous.get("transitions") or 0) + 1
        except (TypeError, ValueError):
            transitions = 1
        payload: dict[str, Any] = {
            "atom": str(atom or "").strip() or None,
            "path": _path_id(process_id, payload_inputs),
            "repo": str(payload_inputs.get("repo") or "").strip() or None,
            "work_id": _work_id(payload_inputs),
            "transitions": transitions,
            "last_progress_at": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }
        payload = {key: value for key, value in payload.items() if value is not None}
        state_dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        tmp.replace(path)
        return payload
    except OSError:
        return None
