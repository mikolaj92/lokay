"""Validate one plan_issue response against the closed executor contract."""

from __future__ import annotations

import json

_SKIP = frozenset({"underspecified", "too_large", "dangerous"})


def validate_plan(raw: str | dict) -> dict:
    """One plan. A JSON string is an agent response; a dict is a built plan.

    A false plan skips with a named reason. A built plan needs a goal and at
    least one file, under files or files_likely.
    """
    if isinstance(raw, dict):
        return _built(raw)
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {"ok": False, "reason": "plan_not_json"}
    if not isinstance(data, dict):
        return {"ok": False, "reason": "plan_not_object"}
    if data.get("ok") is False:
        reason = str(data.get("reason") or "")
        if reason not in _SKIP:
            return {"ok": False, "reason": "plan_reason_unknown"}
        return {"ok": False, "reason": reason, "skip": True}
    files = data.get("files")
    if (
        data.get("ok") is not True
        or not str(data.get("goal") or "").strip()
        or not isinstance(files, list)
        or not files
        or not all(isinstance(item, str) and item.strip() for item in files)
        or not str(data.get("test_command") or "").strip()
    ):
        return {"ok": False, "reason": "plan_incomplete"}
    return {"ok": True, "plan": data}


def _built(plan: dict) -> dict:
    files = plan.get("files") or plan.get("files_likely") or []
    if (
        not str(plan.get("goal") or "").strip()
        or not isinstance(files, list)
        or not files
        or not all(isinstance(item, str) and item.strip() for item in files)
    ):
        return {"ok": False, "reason": "plan_incomplete"}
    return {"ok": True, "plan": plan}
