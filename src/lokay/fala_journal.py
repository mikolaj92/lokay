"""Bound mill Fala sqlite journals. Product recovery stays on state.jsonl."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_MIN_BYTES = 64 * 1024 * 1024
KEEP_ROTATED = 1
_MILL_DBS = (
    ("daemon-cycle", "state.sqlite"),
    ("factory", "state.sqlite"),
)


def rotate_mill_fala_journals(
    *,
    home: Path | None = None,
    min_bytes: int = DEFAULT_MIN_BYTES,
    keep: int = KEEP_ROTATED,
) -> dict[str, Any]:
    """Rename oversized mill journals so the next Fala open starts empty.

    Call only while mill.lock is already held. Live i2pr journals under
    ``fala/i2pr/`` stay. Rename is atomic; a failed rename leaves the live file.
    Pytest must not rotate the operator mill.
    """
    if os.environ.get("PYTEST_CURRENT_TEST") and home is None:
        return {"ok": True, "rotated": [], "reason": "pytest"}
    root = (home or Path.home()) / ".lokay" / "fala"
    rotated: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for folder, name in _MILL_DBS:
        db = (root / folder / name) if folder else (root / name)
        key = db.resolve() if db.exists() else db
        if key in seen:
            continue
        seen.add(key)
        result = _rotate_sqlite(db, min_bytes=max(0, int(min_bytes)), keep=max(0, int(keep)))
        if result is not None:
            rotated.append(result)
    return {"ok": True, "rotated": rotated}


def _rotate_sqlite(db: Path, *, min_bytes: int, keep: int) -> dict[str, Any] | None:
    if not db.is_file():
        return None
    try:
        size = db.stat().st_size
    except OSError:
        return None
    if size < min_bytes:
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = db.with_name(f"{db.name}.{stamp}")
    if dest.exists():
        dest = db.with_name(f"{db.name}.{stamp}.{os.getpid()}")
    try:
        db.replace(dest)
    except OSError:
        return None
    for extra in (f"{db.name}-wal", f"{db.name}-shm"):
        sidecar = db.with_name(extra)
        if sidecar.is_file():
            try:
                sidecar.unlink()
            except OSError:
                pass
    _prune_rotated(db, keep=keep)
    return {"path": str(db), "archived": str(dest), "before_bytes": size}


def _prune_rotated(db: Path, *, keep: int) -> None:
    backups = [
        path
        for path in db.parent.glob(f"{db.name}.*")
        if path.is_file() and not path.name.endswith(("-wal", "-shm"))
    ]
    backups.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
    for stale in backups[keep:]:
        try:
            stale.unlink()
        except OSError:
            pass
