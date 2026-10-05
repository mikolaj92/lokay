"""One place for operator lokay stamp helpers.

Six domains (incident, survey, hygiene, leftover, stale, over-cap) repeated
the same touch/clear/compare helpers under different names. These are the
shared bodies; each domain keeps only its stamp-name constant and the
path derived from config.
"""

from __future__ import annotations

import time
from pathlib import Path


def touch_stamp(stamp: Path | None) -> None:
    """Record now at the stamp path. Silent on OSError — stamps are advisory."""
    if stamp is None:
        return
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(str(int(time.time())), encoding="utf-8")
    except OSError:
        pass


def clear_stamp(stamp: Path | None) -> None:
    if stamp is None:
        return
    try:
        stamp.unlink()
    except OSError:
        pass


def lokay_home_stamp_path(name: str) -> Path:
    """Operator lokay stamp beside ~/.lokay (last-pass / state.jsonl)."""
    return Path.home() / ".lokay" / name


def is_operator_stamp(stamp: Path, name: str) -> bool:
    lokay = lokay_home_stamp_path(name)
    try:
        return stamp.expanduser().resolve() == lokay.resolve()
    except OSError:
        return stamp.expanduser() == lokay
