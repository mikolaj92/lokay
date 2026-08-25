"""Bound every Fala sqlite journal under ~/.lokay/fala/.

The journal is a pass trace, not world history. Each live ``state.sqlite``
has a hard megabyte ceiling. Product recovery stays on state.jsonl.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_MIN_BYTES = 64 * 1024 * 1024
KEEP_ROTATED = 1
_LIVE_JOURNAL = "state.sqlite"


def rotate_mill_fala_journals(
    *,
    home: Path | None = None,
    min_bytes: int = DEFAULT_MIN_BYTES,
    keep: int = KEEP_ROTATED,
) -> dict[str, Any]:
    """Rename oversized Fala journals so the next open starts empty.

    Every live ``state.sqlite`` under ``~/.lokay/fala/`` is in scope, including
    the child journal at the tree root. Call only while mill.lock is already
    held. Rename is atomic; a failed rename of an over-cap file is fail-closed.
    Pytest must not rotate the operator mill.
    """
    if os.environ.get("PYTEST_CURRENT_TEST") and home is None:
        return {"ok": True, "rotated": [], "reason": "pytest"}
    root = (home or Path.home()) / ".lokay" / "fala"
    rotated: list[dict[str, Any]] = []
    ceiling = max(0, int(min_bytes))
    retained = max(0, int(keep))
    for db in _iter_live_journals(root):
        result = _rotate_sqlite(db, min_bytes=ceiling, keep=retained)
        if result is not None:
            rotated.append(result)
    return {"ok": True, "rotated": rotated}


def _iter_live_journals(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    found: list[Path] = []
    seen: set[Path] = set()
    for db in root.rglob(_LIVE_JOURNAL):
        if not db.is_file() or db.name != _LIVE_JOURNAL:
            continue
        try:
            key = db.resolve()
        except OSError:
            key = db
        if key in seen:
            continue
        seen.add(key)
        found.append(db)
    found.sort(key=lambda path: str(path))
    return found


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
    except OSError as exc:
        raise OSError(f"cannot cut over-cap Fala journal {db}: {exc}") from exc
    for extra in (f"{db.name}-wal", f"{db.name}-shm"):
        sidecar = db.with_name(extra)
        if sidecar.is_file():
            try:
                sidecar.unlink()
            except OSError:
                pass
    _prune_rotated(db, keep=keep, retain=dest)
    return {"path": str(db), "archived": str(dest), "before_bytes": size}


def _prune_rotated(db: Path, *, keep: int, retain: Path | None = None) -> None:
    backups = [
        path
        for path in db.parent.glob(f"{db.name}.*")
        if path.is_file() and not path.name.endswith(("-wal", "-shm"))
    ]
    backups.sort(
        key=lambda path: (
            path.stat().st_mtime if path.exists() else 0,
            path.name,
        ),
        reverse=True,
    )
    if retain is not None:
        backups.sort(key=lambda path: path.resolve() != retain.resolve())
    for stale in backups[keep:]:
        try:
            stale.unlink()
        except OSError:
            pass
