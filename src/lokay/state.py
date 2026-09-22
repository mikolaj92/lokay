from __future__ import annotations

import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def append_event(path: Path, event: dict[str, Any], *, durable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        **event,
    }
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        with path.open("a+b") as fh:
            # A killed writer may leave an unterminated (even partial UTF-8)
            # record. Under the shared writer/compactor lock, isolate that tail
            # before appending so a successful fsync means a recoverable record.
            fh.seek(0, os.SEEK_END)
            separator = b""
            if fh.tell():
                fh.seek(-1, os.SEEK_END)
                if fh.read(1) != b"\n":
                    separator = b"\n"
            fh.write(separator + (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
            fh.flush()
            if durable:
                os.fsync(fh.fileno())
        if durable:
            fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
