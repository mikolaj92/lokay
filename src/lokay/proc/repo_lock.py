"""Repo-scoped OS lock for one coding slot.

Identity is `{state.path.parent}/repo-locks/{owner}__{name}.lock`.
Acquire is exclusive and non-blocking. The file is never unlinked; process
death releases the flock. Occupancy/status only probe the lock.
"""

from __future__ import annotations

import fcntl
import os
from pathlib import Path

from lokay.preflight import _safe_owned_path
from lokay.proc.repo_mutex import parse_repo


def repo_lock_dir(config_path: str | None = None) -> Path:
    """Lock directory next to configured state, else `~/.lokay/repo-locks`."""
    if config_path or os.environ.get("LOKAY_CONFIG"):
        try:
            from lokay.config import load_config

            cfg = load_config(config_path)
            return cfg.state_path.parent / "repo-locks"
        except (OSError, ValueError, FileNotFoundError):
            pass
    return Path.home() / ".lokay" / "repo-locks"


def repo_lock_path(state_dir: Path, repo: str) -> Path:
    owner, name = parse_repo(repo).split("/", 1)
    return Path(state_dir) / "repo-locks" / f"{owner}__{name}.lock"


def acquire_repo_lock(path: Path):
    """Return an exclusive lock handle, or ``None`` when the repo is busy."""
    path = Path(path).expanduser()
    if not _safe_owned_path(path.parent):
        return None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a+", encoding="utf-8")
    except OSError:
        return None
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, BlockingIOError):
        handle.close()
        return None
    try:
        os.set_inheritable(handle.fileno(), True)
    except OSError:
        handle.close()
        return None
    return handle


def inspect_repo_lock(path: Path) -> dict:
    """Read occupancy without acquiring or deleting the lock file."""
    path = Path(path).expanduser()
    payload = {"ok": True, "busy": False, "path": str(path)}
    if not path.is_file():
        return payload
    try:
        probe = path.open("r", encoding="utf-8")
    except OSError as exc:
        return {"ok": True, "busy": True, "path": str(path), "reason": "unknown", "error": str(exc)}
    try:
        try:
            fcntl.flock(probe.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(probe.fileno(), fcntl.LOCK_UN)
        except BlockingIOError:
            payload["busy"] = True
        return payload
    finally:
        probe.close()
