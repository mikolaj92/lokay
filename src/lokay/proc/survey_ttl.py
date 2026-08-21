"""Fail-closed TTL for empty factory_pass GitHub surveys.

Idle ticks listed open PRs, inbox, and work:ready every pass (~2s) even when
all three were empty. After a complete empty mill survey, stamp beside mill
state and skip those GitHub lists for 120s. Missing stamp always probes.
Skip does not refresh the stamp, matching leftover closeout / over_cap TTL.
A non-empty survey or a survey_error clears the stamp.
"""

from __future__ import annotations

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
