"""Physical timestamp operations for stale implementation-stage probes."""

import os
import time
from pathlib import Path
from typing import Any

from lokay.operator_stamps import clear_stamp, is_operator_stamp, touch_stamp

STALE_TTL_SECONDS = 300
IDLE_STALE_TTL_SECONDS = 900
STALE_STAMP_NAME = "reap-stale-implementing.stamp"


def stale_stamp_path(cfg: Any) -> Path | None:
    path = getattr(cfg, "state_path", None)
    return Path(path).expanduser().parent / STALE_STAMP_NAME if path else None






def stale_recently_empty(
    stamp: Path | None, *, now: float | None = None, ttl: int | None = None
) -> bool:
    if stamp is None:
        return False
    try:
        age = (now if now is not None else time.time()) - stamp.stat().st_mtime
    except OSError:
        return False
    return 0 <= age < (STALE_TTL_SECONDS if ttl is None else ttl)


def touch_stale_stamp(stamp: Path | None) -> None:
    touch_stamp(stamp)


def clear_stale_stamp(stamp: Path | None) -> None:
    clear_stamp(stamp)
