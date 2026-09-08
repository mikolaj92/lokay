"""Bound every Fala sqlite journal under ~/.lokay/fala/.

The journal is a pass trace, not world history. Each live ``state.sqlite``
has a hard megabyte ceiling. Product recovery stays on state.jsonl.
Lokay never mutates those files directly: Fala ``maintain_journal`` owns
retention, trigger restoration, and VACUUM. Heartbeat leftover ``created``
runs are finalized then deleted; self-repair incomplete runs are finalized
as ``timed_out`` evidence and kept (prepare / ancestry read them).
"""

from __future__ import annotations

import os
import secrets
import shutil
import time
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
    "factory_pass": "factory-pass",
}
_HEARTBEAT_JOURNALS = frozenset(
    {
        "daemon-entry",
        "daemon-cycle",
        "product-entry",
        "product-pass-budget",
        "factory",
        "factory_begin",
        "child-harvest",
        "child_harvest",
    }
)
SUBFLOW_JOURNAL_KINDS = frozenset(
    {
        "coding-execution",
        "i2pr",
        "i2pr-delivery",
        "test-local-execution",
        "pr-repair",
        "pr-triage",
        "issue-split",
    }
)
# Run statuses that are not terminal. Matches read_self_repair_validation_outcome.
_SELF_REPAIR_INCOMPLETE = frozenset(
    {"created", "running", "ready", "pending", "leased"}
)
_HEARTBEAT_INCOMPLETE = frozenset({"created"})


def maintain_lokay_fala_journals(
    *,
    home: Path | None = None,
    min_bytes: int = DEFAULT_MIN_BYTES,
    keep: int = KEEP_ROTATED,
) -> dict[str, Any]:
    """Reclaim oversized Fala journals through the supported host API.

    Every live ``state.sqlite`` under ``~/.lokay/fala/`` is in scope, including
    the child journal at the tree root. Call only while lokay.lock is already
    held. Sidecars stay under Fala; a failed maintain of an over-cap file is
    fail-closed. Pytest must not maintain the operator lokay. Detached
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
    pruned = prune_stale_fala_journals(root)
    from lokay.state_compact import compact_state
    state_path = (home or Path.home()) / ".lokay" / "state.jsonl"
    compacted = compact_state(state_path)
    return {
        "ok": True,
        "maintained": maintained,
        "pruned_journals": pruned,
        "compacted_state": compacted,
    }


def prune_stale_fala_journals(
    root: Path, *, max_age_days: float = 7.0, now: float | None = None
) -> dict[str, Any]:
    """Drop completed per-issue/subflow fala journal directories older than max_age_days."""
    if not root.is_dir():
        return {"pruned_count": 0, "freed_bytes": 0}
    cutoff = (now if now is not None else time.time()) - (max_age_days * 86400)
    pruned_count = 0
    freed_bytes = 0
    for kind in SUBFLOW_JOURNAL_KINDS:
        kind_dir = root / kind
        if not kind_dir.is_dir():
            continue
        try:
            children = list(kind_dir.iterdir())
        except OSError:
            continue
        for child in children:
            if not child.is_dir() or child.is_symlink():
                continue
            try:
                mtime = child.stat().st_mtime
            except OSError:
                continue
            if mtime < cutoff:
                s = sum(
                    f.stat().st_size
                    for f in child.rglob("*")
                    if f.is_file() and not f.is_symlink()
                )
                shutil.rmtree(child, ignore_errors=True)
                pruned_count += 1
                freed_bytes += s
    return {"pruned_count": pruned_count, "freed_bytes": freed_bytes}


rotate_lokay_fala_journals = maintain_lokay_fala_journals


def wrapper_journal_dir(path_id: str, *, home: Path | None = None) -> Path:
    """Fresh sqlite for one heartbeat wrapper host. Not the shared lokay journal.

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


def _is_self_repair_journal(db: Path) -> bool:
    """Journals named self_repair / self_repair_* hold repair evidence."""
    return db.parent.name.startswith("self_repair")


def _reclaim_policy(db: Path) -> tuple[frozenset[str], str, bool] | None:
    """Incomplete statuses, finalize reason, and whether to delete after."""
    if _is_heartbeat_journal(db):
        return _HEARTBEAT_INCOMPLETE, "heartbeat_reclaim", True
    if _is_self_repair_journal(db):
        return _SELF_REPAIR_INCOMPLETE, "self_repair_reclaim", False
    return None


def reclaim_self_repair_incomplete_journals(
    *,
    home: Path | None = None,
) -> dict[str, Any]:
    """Finalize incomplete self-repair runs; keep rows as timeout evidence.

    Fail-soft for organ callers: busy/corrupt journals are skipped. Pytest
    without an explicit home must not touch the operator lokay.
    """
    if os.environ.get("PYTEST_CURRENT_TEST") and home is None:
        return {"ok": True, "reclaimed": [], "reason": "pytest"}
    root = (home or Path.home()) / ".lokay" / "fala"
    reclaimed: list[dict[str, Any]] = []
    for db in _iter_live_journals(root):
        if not _is_self_repair_journal(db):
            continue
        try:
            count = _reclaim_incomplete_runs(db)
        except Exception as exc:
            if _skip_busy_or_corrupt(exc):
                continue
            raise
        if count:
            reclaimed.append({"path": str(db), "reclaimed": count})
    return {"ok": True, "reclaimed": reclaimed}


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


def _reclaim_incomplete_runs(db: Path) -> int:
    """Finalize incomplete runs per journal policy; optionally delete."""
    policy = _reclaim_policy(db)
    if policy is None:
        return 0
    statuses, reason, delete_after = policy
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
        if str(run.get("status") or "") not in statuses:
            continue
        run_id = str(run.get("id") or "").strip()
        if not run_id:
            continue
        try:
            fala.finalize_run(
                db,
                run_id=run_id,
                status="timed_out",
                reason=reason,
            )
            if delete_after:
                fala.delete_terminal_run(db, run_id)
        except AttributeError:
            return reclaimed
        except Exception as exc:
            if _skip_busy_or_corrupt(exc):
                return reclaimed
            continue
        reclaimed += 1
    return reclaimed


def _reclaim_created_runs(db: Path) -> int:
    """Backward-compatible alias used by maintain; prefer policy helper."""
    return _reclaim_incomplete_runs(db)


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
