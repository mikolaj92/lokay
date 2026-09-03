"""Bound every Fala sqlite journal under ~/.lokay/fala/.

The journal is a pass trace, not world history. Each live ``state.sqlite``
has a hard megabyte ceiling. Product recovery stays on state.jsonl.
Lokay never mutates those files directly: Fala ``maintain_journal`` owns
retention, trigger restoration, and VACUUM. Killed heartbeat runs left in
``created`` are finalized through ``finalize_run`` first, so retention can
see them.
"""

from __future__ import annotations

import os
import secrets
import shutil
from pathlib import Path
from typing import Any

DEFAULT_MIN_BYTES = 64 * 1024 * 1024
KEEP_ROTATED = 1
CREATED_RECLAIM_PER_JOURNAL = 8
WRAPPER_KEEP = 2
_LIVE_JOURNAL = "state.sqlite"
_WRAPPER_PREFIXES = {
    "daemon_entry": "daemon-entry",
    "daemon_cycle": "daemon-cycle",
}
_HEARTBEAT_JOURNALS = frozenset(
    {
        "daemon-entry",
        "daemon-cycle",
        "product-entry",
        "product-pass-budget",
        "factory",
        "factory_begin",
    }
)


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
    fail-closed. Pytest must not maintain the operator mill. Detached
    issue-to-PR journals are not finalized.
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


def wrapper_journal_dir(path_id: str, *, home: Path | None = None) -> Path:
    """Fresh sqlite for one heartbeat wrapper host. Not the shared mill journal.

    ``daemon_entry`` / ``daemon_cycle`` are a pass trace. Reopening a 59 MiB
    journal of killed ``created`` runs burns the 180s ceiling. Each tick gets
    its own directory; older wrapper dirs are pruned. Detached issue-to-PR
    journals are not in this family.
    """
    prefix = _WRAPPER_PREFIXES.get(str(path_id))
    if not prefix:
        raise ValueError(f"unknown heartbeat wrapper path: {path_id}")
    root = (home or Path.home()) / ".lokay" / "fala"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{prefix}-{os.getpid()}-{secrets.token_hex(6)}"
    path.mkdir(parents=True, exist_ok=False)
    _prune_wrapper_journals(root, prefix=prefix, keep_path=path, keep=WRAPPER_KEEP)
    return path


def _prune_wrapper_journals(
    root: Path, *, prefix: str, keep_path: Path, keep: int
) -> None:
    retained = max(1, int(keep))
    try:
        dirs = [
            path
            for path in root.iterdir()
            if path.is_dir() and path.name.startswith(f"{prefix}-")
        ]
    except OSError:
        return
    dirs.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
    kept = 0
    for path in dirs:
        if path.resolve() == keep_path.resolve():
            kept += 1
            continue
        if kept < retained:
            kept += 1
            continue
        shutil.rmtree(path, ignore_errors=True)


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


def _is_heartbeat_journal(db: Path) -> bool:
    parent = db.parent.name
    if parent in _HEARTBEAT_JOURNALS:
        return True
    if parent.startswith("factory-slot-"):
        return True
    return parent == "fala"


def _skip_busy_or_corrupt(exc: BaseException) -> bool:
    if isinstance(exc, AttributeError):
        return True
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "locked",
            "busy",
            "invalid status",
            "invalid run",
            "not a database",
            "has no attribute",
        )
    )


def _reclaim_created_runs(db: Path) -> int:
    """Finalize and delete killed heartbeat runs that never left created."""
    if not _is_heartbeat_journal(db):
        return 0
    import fala

    try:
        runs = fala.list_runs(db)
    except Exception as exc:
        if _skip_busy_or_corrupt(exc):
            return 0
        raise
    reclaimed = 0
    for run in runs:
        if reclaimed >= CREATED_RECLAIM_PER_JOURNAL:
            break
        if not isinstance(run, dict):
            continue
        if str(run.get("status") or "") != "created":
            continue
        run_id = str(run.get("id") or "").strip()
        if not run_id:
            continue
        try:
            fala.finalize_run(
                db,
                run_id=run_id,
                status="timed_out",
                reason="heartbeat_reclaim",
            )
            fala.delete_terminal_run(db, run_id)
        except AttributeError:
            return reclaimed
        except Exception as exc:
            if _skip_busy_or_corrupt(exc):
                return reclaimed
            continue
        reclaimed += 1
    return reclaimed


def _maintain_sqlite(db: Path, *, min_bytes: int, keep: int) -> dict[str, Any] | None:
    if not db.is_file():
        return None
    try:
        size = db.stat().st_size
    except OSError:
        return None
    try:
        reclaimed = _reclaim_created_runs(db)
    except Exception as exc:
        if _skip_busy_or_corrupt(exc):
            reclaimed = 0
        else:
            raise
    if size < min_bytes:
        if reclaimed == 0:
            return None
        return {
            "path": str(db),
            "before_bytes": size,
            "deleted_run_count": reclaimed,
            "reclaimed_created": reclaimed,
            "vacuumed": False,
        }
    import fala

    try:
        applied = fala.maintain_journal(
            db,
            older_than_days=0,
            keep_last=keep,
            vacuum=True,
            dry_run=False,
        )
    except Exception as exc:  # noqa: BLE001
        if _skip_busy_or_corrupt(exc):
            if reclaimed == 0:
                return None
            return {
                "path": str(db),
                "before_bytes": size,
                "deleted_run_count": reclaimed,
                "reclaimed_created": reclaimed,
                "vacuumed": False,
            }
        raise
    return {
        "path": str(db),
        "before_bytes": size,
        "deleted_run_count": int(applied.get("deleted_run_count") or 0) + reclaimed,
        "reclaimed_created": reclaimed,
        "vacuumed": bool(applied.get("vacuumed")),
    }
