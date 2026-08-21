"""Fail-closed TTL for empty factory_pass GitHub surveys.

Idle ticks listed open PRs, inbox, and work:ready every pass (~2s) even when
all three were empty. After a complete empty mill survey, stamp beside mill
state and skip those GitHub lists for 120s. Missing stamp always probes.
Skip does not refresh the stamp, matching leftover closeout / over_cap TTL.
A non-empty survey or a survey_error clears the stamp.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

SURVEY_TTL_SECONDS = 120
SURVEY_STAMP_NAME = "factory-survey.stamp"


def survey_stamp_path(begin: dict[str, Any] | None) -> Path | None:
    """Stamp lives beside mill state. Missing path means always probe."""
    if not begin:
        return None
    path = begin.get("state_path") or begin.get("stuck_path")
    if not path:
        return None
    parent = Path(str(path)).expanduser().parent
    if not parent.as_posix():
        return None
    return parent / SURVEY_STAMP_NAME


def survey_recently_empty(stamp: Path | None, *, now: float | None = None) -> bool:
    if stamp is None:
        return False
    try:
        age = (now if now is not None else time.time()) - stamp.stat().st_mtime
    except OSError:
        return False
    return 0 <= age < SURVEY_TTL_SECONDS


def touch_survey_stamp(stamp: Path | None) -> None:
    if stamp is None:
        return
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(str(int(time.time())), encoding="utf-8")
    except OSError:
        pass


def clear_survey_stamp(stamp: Path | None) -> None:
    if stamp is None:
        return
    try:
        stamp.unlink()
    except OSError:
        pass


def mill_survey_stamp_path() -> Path:
    """Operator mill stamp beside last-pass / state.jsonl."""
    return Path.home() / ".lokay" / SURVEY_STAMP_NAME


def last_pass_is_empty_idle(receipt: dict[str, Any] | None) -> bool:
    if not isinstance(receipt, dict):
        return False
    if receipt.get("health") != "idle" and not receipt.get("idle"):
        return False
    remaining = receipt.get("remaining")
    if not isinstance(remaining, dict):
        return False
    work = (
        int(remaining.get("inbox") or 0)
        + int(remaining.get("ready") or 0)
        + int(remaining.get("open_ai_prs") or 0)
        + int(remaining.get("issue_to_pr_started") or 0)
        + int(remaining.get("survey_errors") or 0)
    )
    if work:
        return False
    by_repo = remaining.get("by_repo") or receipt.get("by_repo") or []
    if isinstance(by_repo, list) and any(
        isinstance(row, dict) and bool(row.get("occupied")) for row in by_repo
    ):
        return False
    return True


def skip_idle_factory_pass(
    *,
    live: bool,
    stamp: Path | None = None,
    receipt: dict[str, Any] | None = None,
    now: float | None = None,
) -> dict[str, Any] | None:
    """Skip hosting factory_pass while a live idle mill has a fresh empty survey.

    Missing / unreadable stamp or last-pass always hosts. Skip does not
    refresh the stamp. Pytest must not skip the operator mill.
    """
    if not live:
        return None
    if os.environ.get("PYTEST_CURRENT_TEST") and stamp is None:
        return None
    if stamp is None:
        stamp = mill_survey_stamp_path()
    if not survey_recently_empty(stamp, now=now):
        return None
    if receipt is None:
        from lokay.pass_receipt import read_pass_receipt

        receipt = read_pass_receipt()
    if not last_pass_is_empty_idle(receipt):
        return None
    remaining = receipt.get("remaining") if isinstance(receipt, dict) else {}
    return {
        "ok": True,
        "health": "idle",
        "idle": True,
        "live": True,
        "progress": 0,
        "remaining": remaining if isinstance(remaining, dict) else {},
        "skipped": True,
        "reason": "recent_empty_survey",
    }
