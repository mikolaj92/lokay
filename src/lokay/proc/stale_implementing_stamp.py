"""Physical timestamp operations for stale implementation-stage probes."""

import os, time
from pathlib import Path
from typing import Any

STALE_TTL_SECONDS = 300
IDLE_STALE_TTL_SECONDS = 900
STALE_STAMP_NAME = "reap-stale-implementing.stamp"


def stale_stamp_path(cfg: Any) -> Path | None:
    path = getattr(cfg, "state_path", None)
    return Path(path).expanduser().parent / STALE_STAMP_NAME if path else None


def lokay_stale_stamp_path() -> Path:
    return Path.home() / ".lokay" / STALE_STAMP_NAME


def _is_operator_lokay_stale_stamp(stamp: Path) -> bool:
    try:
        return stamp.expanduser().resolve() == lokay_stale_stamp_path().resolve()
    except OSError:
        return stamp.expanduser() == lokay_stale_stamp_path()


def stale_recently_empty(
    stamp: Path | None, *, now: float | None = None, ttl: int | None = None
) -> bool:
    if stamp is None:
        return False
    if os.environ.get("PYTEST_CURRENT_TEST") and _is_operator_lokay_stale_stamp(stamp):
        return False
    try:
        age = (now if now is not None else time.time()) - stamp.stat().st_mtime
    except OSError:
        return False
    return 0 <= age < (STALE_TTL_SECONDS if ttl is None else ttl)


def touch_stale_stamp(stamp: Path | None) -> None:
    if stamp is None:
        return
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(str(int(time.time())), encoding="utf-8")
    except OSError:
        pass


def clear_stale_stamp(stamp: Path | None) -> None:
    if stamp is None:
        return
    try:
        stamp.unlink()
    except OSError:
        pass
