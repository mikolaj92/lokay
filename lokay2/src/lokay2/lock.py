from __future__ import annotations

import json
import os
from pathlib import Path

STATE = Path.home() / ".lokay2" / "locks"


def lock_path(owner: str, repo: str) -> Path:
    safe = repo.replace("/", "__")
    return STATE / f"{owner}__{safe}.lock"


def acquire(owner: str, repo: str) -> dict:
    path = lock_path(owner, repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return {"result": "busy", "path": str(path)}
    os.write(fd, str(os.getpid()).encode())
    return {"result": "held", "fd": fd, "path": str(path)}


def release(held: dict) -> None:
    fd = held.get("fd")
    if not isinstance(fd, int):
        return
    import fcntl

    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)


def emit_lock(payload: dict) -> None:
    public = {k: v for k, v in payload.items() if k != "fd"}
    print(json.dumps(public, separators=(",", ":")))
