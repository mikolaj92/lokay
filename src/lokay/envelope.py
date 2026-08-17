from __future__ import annotations

import json
import sys
from typing import Any


def ok(**fields: Any) -> dict[str, Any]:
    return {"ok": True, **fields}


def err(message: str, **fields: Any) -> dict[str, Any]:
    return {"ok": False, "error": message, **fields}


def emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def _as_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _remaining_of(payload: dict[str, Any]) -> dict[str, Any]:
    remaining = payload.get("remaining")
    return remaining if isinstance(remaining, dict) else {}


def mill_glance(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Best-effort health/progress/remaining from a daemon or mill envelope."""
    if not isinstance(payload, dict):
        return {}
    sources: list[dict[str, Any]] = [payload]
    mill = _as_dict(payload.get("mill"))
    if mill is not None:
        sources.append(mill)
    last = _as_dict(payload.get("last"))
    if last is not None:
        sources.append(last)
    terminal = _as_dict(payload.get("terminal"))
    if terminal is not None:
        recovery_mill = _as_dict(terminal.get("recovery_mill"))
        if recovery_mill is not None:
            nested = _as_dict(recovery_mill.get("mill"))
            sources.append(nested if nested is not None else recovery_mill)
    for src in sources:
        health = str(src.get("health") or "")
        remaining = _remaining_of(src)
        started = int(remaining.get("issue_to_pr_started") or 0)
        progress = int(src.get("progress") or 0)
        if health == "progress" or started > 0 or progress > 0:
            return {
                "health": health or ("progress" if started or progress else ""),
                "progress": max(progress, started),
                "remaining": remaining,
                "ok": src.get("ok"),
            }
    return {
        "health": str(payload.get("health") or ""),
        "progress": int(payload.get("progress") or 0),
        "remaining": _remaining_of(payload),
        "ok": payload.get("ok"),
    }


_WRAPPER_HEALTH = frozenset({"", "failed", "error", "unknown"})


def _productive(glance: dict[str, Any]) -> bool:
    if str(glance.get("health") or "") == "progress":
        return True
    if int(glance.get("progress") or 0) > 0:
        return True
    remaining = glance.get("remaining")
    return isinstance(remaining, dict) and int(remaining.get("issue_to_pr_started") or 0) > 0


def process_exit_code(
    payload: dict[str, Any] | None,
    *,
    last_pass: dict[str, Any] | None = None,
) -> int:
    """LaunchAgent status: 0 when the pass did work, even if Fala ``ok`` is false.

    Productive work is ``health=progress``, ``progress>0``, or detached
    ``issue_to_pr_started``. last-pass may confirm those signals only when the
    current envelope is a Fala wrapper that hid mill health.
    """
    if isinstance(payload, dict) and payload.get("ok", False):
        return 0
    current = mill_glance(payload)
    if _productive(current):
        return 0
    if isinstance(payload, dict) and (
        str(payload.get("health") or "") == "host_updated"
        or str(payload.get("reason") or "") == "host_updated"
    ):
        return 0
    current_health = str(current.get("health") or "")
    if current_health not in _WRAPPER_HEALTH:
        return 1
    return 0 if _productive(mill_glance(last_pass)) else 1


def emit_exit(payload: dict[str, Any], code: int | None = None) -> int:
    emit(payload)
    if code is not None:
        return code
    return 0 if payload.get("ok", False) else 1


def read_stdin_json() -> dict[str, Any] | list[Any] | None:
    raw = sys.stdin.read().strip()
    if not raw:
        return None
    return json.loads(raw)
