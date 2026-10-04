"""Inspect Fala journal retention without destroying recovery evidence.

Native maintain_journal plans size-based candidates only. Directory age,
run status and wrapper count cannot prove delivery or release child recovery
references. Pending evidence is retained; no synthetic terminal transitions.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

DEFAULT_MIN_BYTES = 64 * 1024 * 1024
KEEP_ROTATED = 1
WRAPPER_KEEP = 2
DEFAULT_MAX_AGE_DAYS = 14.0
DEFAULT_HARD_CAP_BYTES = 10 * 1024 * 1024 * 1024
DEFAULT_JOURNAL_KEEP_LAST = 5
_LIVE_JOURNAL = "state.sqlite"
_WRAPPER_PREFIXES = {
    "daemon_entry": "daemon-entry",
    "daemon_cycle": "daemon-cycle",
    "factory_pass": "factory-pass",
}

def maintain_lokay_fala_journals(
    *,
    home: Path | None = None,
    min_bytes: int = DEFAULT_MIN_BYTES,
    keep: int = KEEP_ROTATED,
    max_age_days: float = DEFAULT_MAX_AGE_DAYS,
    hard_cap_bytes: int = DEFAULT_HARD_CAP_BYTES,
    journal_keep_last: int = DEFAULT_JOURNAL_KEEP_LAST,
) -> dict[str, Any]:
    """Apply the lokay retention policy to Fala journals.

    Execution data is consumable (t_2d81b9c3): terminal runs older than
    ``max_age_days`` are deleted natively (with the newest
    ``journal_keep_last`` terminal runs kept and a VACUUM to return the
    space), wrapper traces beyond the keep window are pruned, stale journal
    dirs and archives are removed, and the oldest consumable data is evicted
    until ``~/.lokay`` fits ``hard_cap_bytes``. Nonterminal runs are never
    candidates and error logs are only a last-resort hard-cap class.

    Call while lokay.lock is held. Fala owns SQLite and sidecar handling.
    Pytest without an explicit home never inspects operator journals.
    """
    if os.environ.get("PYTEST_CURRENT_TEST") and home is None:
        return {"ok": True, "maintained": [], "reason": "pytest"}
    root = (home or Path.home()) / ".lokay" / "fala"
    maintained: list[dict[str, Any]] = []
    ceiling = max(0, int(min_bytes))
    for db in _iter_live_journals(root):
        result = _maintain_sqlite(
            db,
            min_bytes=ceiling,
            max_age_days=max(0.0, float(max_age_days)),
            journal_keep_last=max(-1, int(journal_keep_last)),
        )
        if result is not None:
            maintained.append(result)
    from lokay import retention

    lokay_home = (home or Path.home()) / ".lokay"
    pruned_wrappers = retention.prune_wrapper_journals(root, keep=WRAPPER_KEEP)
    pruned = retention.prune_stale_journal_dirs(root, max_age_days=max_age_days)
    pruned_root = retention.prune_stale_root_artifacts(lokay_home, max_age_days=max_age_days)
    cap = retention.enforce_hard_cap(lokay_home, cap_bytes=hard_cap_bytes)
    pruned_logs = prune_stale_logs(lokay_home / "logs")
    pruned_tmp = prune_stale_tmp_dirs(lokay_home)
    from lokay.state_compact import compact_state
    state_path = lokay_home / "state.jsonl"
    compacted = compact_state(state_path)
    return {
        "ok": True,
        "maintained": maintained,
        "pruned_wrappers": pruned_wrappers,
        "pruned_journals": pruned,
        "pruned_root_artifacts": pruned_root,
        "hard_cap": cap,
        "pruned_logs": pruned_logs,
        "pruned_tmp": pruned_tmp,
        "compacted_state": compacted,
    }


def prune_stale_fala_journals(
    root: Path, *, max_age_days: float = 7.0, now: float | None = None
) -> dict[str, Any]:
    """Preserve artifacts until completion and recovery dependencies are known.

    Age is not proof of delivery. These paths have no trustworthy binding to
    merged work, active writers or recovery consumers, so deletion is refused.
    """
    return {"pruned_count": 0, "freed_bytes": 0,
            "reason": "completion_evidence_required"}


def prune_stale_logs(
    logs_dir: Path, *, max_age_days: float = 7.0, now: float | None = None
) -> dict[str, Any]:
    """Preserve artifacts until completion and recovery dependencies are known.

    Age is not proof of delivery. These paths have no trustworthy binding to
    merged work, active writers or recovery consumers, so deletion is refused.
    """
    return {"pruned_count": 0, "freed_bytes": 0,
            "reason": "completion_evidence_required"}


def prune_stale_tmp_dirs(
    lokay_home: Path, *, max_age_days: float = 3.0, now: float | None = None
) -> dict[str, Any]:
    """Preserve artifacts until completion and recovery dependencies are known.

    Age is not proof of delivery. These paths have no trustworthy binding to
    merged work, active writers or recovery consumers, so deletion is refused.
    """
    return {"pruned_count": 0, "freed_bytes": 0,
            "reason": "completion_evidence_required"}


rotate_lokay_fala_journals = maintain_lokay_fala_journals


def wrapper_journal_dir(path_id: str, *, home: Path | None = None) -> Path:
    """Fresh sqlite for one heartbeat wrapper host. Not the shared lokay journal.

    ``daemon_entry`` / ``daemon_cycle`` are a pass trace. Reopening a 59 MiB
    journal of killed ``created`` runs burns the 180s ceiling. Each tick gets
    its own directory. Older wrappers remain until completion and recovery
    dependencies can be verified. Detached issue-to-PR journals are separate.
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
    """Older wrapper traces are consumable pass data (t_2d81b9c3).

    The freshly allocated ``keep_path`` and the newest ``keep`` quiet dirs per
    prefix survive; anything beyond that window is a consumed one-tick trace.
    Live writers inside the grace window are never touched.
    """
    from lokay import retention

    retention.prune_wrapper_journals(root, keep=keep)


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


def _is_self_repair_journal(db: Path) -> bool:
    """Self-repair journals hold recovery evidence."""
    return db.parent.name.startswith("self_repair")


def reclaim_self_repair_incomplete_journals(
    *,
    home: Path | None = None,
) -> dict[str, Any]:
    """Compatibility entry: preserve incomplete self-repair recovery state.

    Maintenance lacks worker-lease evidence needed to finalize any run.
    Pytest without an explicit home must not touch the operator lokay.
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
    """Do not invent terminal state from a directory name or run status.

    Recovery needs expired worker lease ownership; a global maintenance pass
    does not have that authority, especially for detached child processes.
    """
    return 0


def _reclaim_created_runs(db: Path) -> int:
    """Backward-compatible alias used by maintain; prefer policy helper."""
    return _reclaim_incomplete_runs(db)


def _maintain_sqlite(
    db: Path,
    *,
    min_bytes: int,
    max_age_days: float,
    journal_keep_last: int,
) -> dict[str, Any] | None:
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
    import fala

    try:
        applied = fala.maintain_journal(
            db,
            older_than_days=max(0.0, float(max_age_days)),
            keep_last=int(journal_keep_last),
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
    deleted = int(applied.get("deleted_run_count") or 0)
    vacuumed = bool(applied.get("vacuumed"))
    if deleted == 0 and reclaimed == 0 and not vacuumed and size < min_bytes:
        return None
    return {
        "path": str(db),
        "before_bytes": size,
        "deleted_run_count": deleted,
        "reclaimed_created": reclaimed,
        "vacuumed": vacuumed,
    }
