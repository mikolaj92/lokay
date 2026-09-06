"""Stamp one terminated receipt without hiding it from harvest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lokay.proc.detach_issue_to_pr import issue_to_pr_receipt_path

_IDENTITY = ("repo", "issue", "pid", "launch_id")


def stamp_receipt_file(path: Path, receipt: dict[str, Any], *, reason: str | None) -> bool:
    """Write a terminal reaped receipt; clear implementing; keep identity."""
    row = {
        key: value
        for key, value in dict(receipt).items()
        if not str(key).startswith("_")
    }
    row.update(ok=False, reason=reason, reaped=True)
    # Implementing without a live pid is a lie — omit state (reason carries terminal).
    row.pop("state", None)
    try:
        Path(path).write_text(json.dumps(row), encoding="utf-8")
        return True
    except OSError:
        return False


def stamp(terminated: dict) -> dict:
    receipt = dict(terminated.get("receipt") or {})
    for key in _IDENTITY:
        if key not in receipt and key in terminated:
            receipt[key] = terminated[key]
    reason = terminated.get("reason")
    written = False
    try:
        path = issue_to_pr_receipt_path(terminated["repo"], int(terminated["issue"]))
        written = stamp_receipt_file(path, receipt, reason=reason)
    except (KeyError, OSError, TypeError, ValueError):
        pass
    return {**terminated, "route": "stamped", "receipt_stamped": written}
