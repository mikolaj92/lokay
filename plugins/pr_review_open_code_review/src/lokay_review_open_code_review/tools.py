"""Validate the v1.12 tool registry against Lokay's non-publication boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_ALLOWED = frozenset({"task_done", "code_comment", "file_read", "file_read_diff", "file_find", "code_search"})
_REQUIRED = frozenset({"task_done", "code_comment", "file_read", "file_read_diff", "file_find", "code_search"})


def validate_tools(path: Path | str) -> dict[str, dict[str, Any]]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("review tool registry unreadable") from exc
    if not isinstance(raw, list):
        raise ValueError("review tool registry must be an array")
    tools: dict[str, dict[str, Any]] = {}
    for row in raw:
        if not isinstance(row, dict) or row.get("name") not in _ALLOWED:
            raise ValueError("review tool registry contains an unapproved tool")
        name = str(row["name"])
        if name in tools or not isinstance(row.get("definition"), dict):
            raise ValueError("review tool registry contains malformed or duplicate tool")
        if not isinstance(row.get("plan_task"), bool) or not isinstance(row.get("main_task"), bool):
            raise ValueError("review tool phase flags must be booleans")
        tools[name] = row
    if set(tools) != _REQUIRED:
        raise ValueError("review tool registry is incomplete")
    if tools["task_done"].get("plan_task") is not False or tools["task_done"].get("main_task") is not True:
        raise ValueError("task_done phase boundary mismatch")
    if tools["code_comment"].get("plan_task") is not False or tools["code_comment"].get("main_task") is not True:
        raise ValueError("code_comment phase boundary mismatch")
    if tools["file_read"].get("plan_task") is not False or tools["file_read"].get("main_task") is not True:
        raise ValueError("file_read phase boundary mismatch")
    for name in ("file_read_diff", "file_find", "code_search"):
        if tools[name].get("plan_task") is not True or tools[name].get("main_task") is not True:
            raise ValueError(f"{name} phase boundary mismatch")
    return tools
