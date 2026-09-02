"""Bound every Fala sqlite journal under ~/.lokay/fala/.

The journal is a pass trace, not world history. Each live ``state.sqlite``
has a hard megabyte ceiling. Product recovery stays on state.jsonl.
Lokay never mutates those files directly: Fala ``maintain_journal`` owns
retention, trigger restoration, and VACUUM.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

DEFAULT_MIN_BYTES = 64 * 1024 * 1024
KEEP_ROTATED = 1
_LIVE_JOURNAL = "state.sqlite"


def maintain_mill_fala_journals(
    *,
    home: Path | None = None,
    min_bytes: int = DEFAULT_MIN_BYTES,
    keep: int = KEEP_ROTATED,
) -> dict[str, Any]:
    """Reclaim oversized Fala journals through the supported host API.

    Every live ``state.sqlite`` under ``~/.lokay/fala/`` is in scope, including
    the child journal at the tree root. Call only while mill.lock is already
    held. Sidecars stay under Fala; a failed maintain of an over-cap file is
    fail-closed. Pytest must not maintain the operator mill.
    """
    if os.environ.get("PYTEST_CURRENT_TEST") and home is None:
        return {"ok": True, "maintained": [], "reason": "pytest"}
    root = (home or Path.home()) / ".lokay" / "fala"
    maintained: list[dict[str, Any]] = []
    ceiling = max(0, int(min_bytes))
    retained = max(0, int(keep))
    for db in _iter_live_journals(root):
        result = _maintain_sqlite(db, min_bytes=ceiling, keep=retained)
        if result is not None:
            maintained.append(result)
    return {"ok": True, "maintained": maintained}


rotate_mill_fala_journals = maintain_mill_fala_journals


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


def _maintain_sqlite(db: Path, *, min_bytes: int, keep: int) -> dict[str, Any] | None:
    if not db.is_file():
        return None
    try:
        size = db.stat().st_size
    except OSError:
        return None
    if size < min_bytes:
        return None
    import fala

    try:
        applied = fala.maintain_journal(
            db,
            older_than_days=0,
            keep_last=keep,
            vacuum=True,
            dry_run=False,
        )
    except Exception as exc:
        text = str(exc).lower()
        if "locked" in text or "busy" in text:
            return None
        raise
    return {
        "path": str(db),
        "before_bytes": size,
        "deleted_run_count": int(applied.get("deleted_run_count") or 0),
        "vacuumed": bool(applied.get("vacuumed")),
    }
