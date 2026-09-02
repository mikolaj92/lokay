"""Read current factory lease facts without acquiring or mutating them."""

from __future__ import annotations

import fcntl
import json
import os
import stat
import time
from pathlib import Path

from lokay.preflight import health_lease_status


def _lock_is_held(path: Path) -> bool:
    if not path.is_file():
        return False
    probe = path.open("r")
    try:
        try:
            fcntl.flock(probe.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(probe.fileno(), fcntl.LOCK_UN)
        except BlockingIOError:
            return True
        return False
    finally:
        probe.close()


def _active_run_lease(state_dir: Path, lock: Path) -> Path | None:
    expected = str(lock.expanduser().absolute())
    now = int(time.time())
    for path in sorted(state_dir.glob("health-lease-*-*"), reverse=True):
        try:
            info = path.lstat()
            if path.is_symlink() or not stat.S_ISREG(info.st_mode):
                continue
            if hasattr(os, "getuid") and info.st_uid != os.getuid():
                continue
            if stat.S_IMODE(info.st_mode) != 0o600:
                continue
            record = json.loads(path.read_text(encoding="ascii"))
            if record.get("lock_path") != expected or int(record["expires_at"]) <= now:
                continue
            os.kill(int(record["owner_pid"]), 0)
            if _lock_is_held(lock):
                return path
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue
    return None


def read(config: dict) -> dict:
    state_dir = Path(config["state_path"]).parent
    lock = state_dir / "mill.lock"
    if os.environ.get("LOKAY_HEALTH_LEASE", ""):
        ok, reason = health_lease_status(lock_path=lock)
        return {
            "ok": True,
            "lease_ok": ok,
            "lease_reason": reason,
            "run_active": ok,
            "run_observation_reason": reason,
        }
    active = _active_run_lease(state_dir, lock)
    return {
        "ok": True,
        "lease_ok": None,
        "lease_reason": "not_observed",
        "run_active": active is not None,
        "run_observation_reason": "active_run" if active else "inactive",
        "run_lease_path": str(active) if active else None,
    }
