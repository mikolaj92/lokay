from __future__ import annotations

from lokay.store import acquire_lock, release_lock

from pathlib import Path

STATE = Path.home() / ".lokay" / "locks"


def lock_path(owner: str, repo: str) -> Path:
    safe = repo.replace("/", "__")
    return STATE / f"{owner}__{safe}.lock"


def acquire(owner: str, repo: str) -> dict:
    return acquire_lock(lock_path(owner, repo))


def release(held: dict) -> None:
    release_lock(held)
