"""Filesystem retention for consumable lokay execution data.

Policy (t_2d81b9c3): execution data is consumable. Code lives in git and
error logs stay. Rows and execution artifacts are removed after age
(default 14 days) and under a hard ``~/.lokay`` cap (default 10 GB) the
oldest data is evicted instead of failing the pass.

Never touched by this module: ``state.jsonl``, ``fail-digests/``,
``decisions.jsonl``, ``recovery-history.jsonl``, ``quarantine/``,
``health-lease*``, git repos and ``worktrees/`` (own reap flow with
unpublished-work protection). ``logs/`` is only evicted as the very last
hard-cap class, oldest first, because error logs are the product's memory
of failures.

SQLite is never edited in place here: whole journal directories are removed
only when they are stale, quiet (no fresh ``-wal`` activity) and hold no
nonterminal runs (checked through Fala's native read API).
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

DEFAULT_MAX_AGE_DAYS = 14.0
DEFAULT_HARD_CAP_BYTES = 10 * 1024 * 1024 * 1024
DEFAULT_WRAPPER_KEEP = 2
DEFAULT_JOURNAL_KEEP_LAST = 5
LIVE_GRACE_SECONDS = 3600.0

_WRAPPER_PREFIXES = ("daemon-cycle", "daemon-entry", "factory-pass")
_ROOT_ARCHIVE_PREFIXES = ("fala-archive-", "fala-retained-", "cleanup-")
_PROTECTED = (
    "state.jsonl",
    "fail-digests",
    "decisions.jsonl",
    "recovery-history.jsonl",
    "quarantine",
    "health-lease",
    "worktrees",
    "repos",
)


def _now(now: float | None) -> float:
    return time.time() if now is None else float(now)


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def is_quiet(path: Path, *, now: float | None = None, grace: float = LIVE_GRACE_SECONDS) -> bool:
    """No live writer: neither the dir nor a fresh ``-wal`` sidecar moved."""
    stamp = _now(now) - grace
    if _mtime(path) > stamp:
        return False
    for sidecar in ("-wal", "-shm"):
        if _mtime(path / f"state.sqlite{sidecar}") > stamp:
            return False
    return True


def dir_size(path: Path) -> int:
    total = 0
    if path.is_file():
        return path.stat().st_size
    try:
        stack = [path]
        while stack:
            current = stack.pop()
            try:
                entries = list(current.iterdir())
            except OSError:
                continue
            for entry in entries:
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir():
                        stack.append(entry)
                    else:
                        total += entry.stat().st_size
                except OSError:
                    continue
    except OSError:
        return total
    return total


def home_size(home: Path) -> int:
    lokay = (home or Path.home()) / ".lokay"
    return dir_size(lokay)


def _remove(path: Path, removed: list[str], *, note: str) -> bool:
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
    except OSError:
        return False
    removed.append(f"{path} ({note})")
    return True


def prune_wrapper_journals(
    root: Path,
    *,
    keep: int = DEFAULT_WRAPPER_KEEP,
    now: float | None = None,
    grace: float = LIVE_GRACE_SECONDS,
) -> dict[str, Any]:
    """Wrapper journals are one-tick pass traces: keep the newest ``keep``.

    Each daemon tick allocates a fresh wrapper dir; older ones are consumed
    traces. Quiet dirs beyond the keep window are deleted; anything written
    inside the live grace is never touched.
    """
    stamp = _now(now)
    removed: list[str] = []
    kept = 0
    for prefix in _WRAPPER_PREFIXES:
        dirs = sorted(
            (d for d in root.glob(f"{prefix}-*") if d.is_dir()),
            key=_mtime,
            reverse=True,
        )
        for index, path in enumerate(dirs):
            if index < max(0, int(keep)):
                kept += 1
                continue
            if _mtime(path) > stamp - grace:
                kept += 1  # possibly a live writer
                continue
            _remove(path, removed, note="wrapper trace beyond keep window")
    return {"removed": removed, "removed_count": len(removed), "kept": kept}


def _has_nonterminal_runs(db: Path) -> bool | None:
    """None means unknown (unreadable journal) — callers must retain."""
    try:
        import fala
    except Exception:
        return None
    try:
        runs = fala.list_runs(db)
    except Exception:
        return None
    terminal = {"completed", "failed", "cancelled", "timed_out"}
    return any(run.get("status") not in terminal for run in runs)


def prune_stale_journal_dirs(
    root: Path,
    *,
    max_age_days: float = DEFAULT_MAX_AGE_DAYS,
    now: float | None = None,
    grace: float = LIVE_GRACE_SECONDS,
) -> dict[str, Any]:
    """Delete whole journal dirs that are old, quiet and hold only terminal runs.

    Per-issue and per-family Fala journals accumulate forever; once every run
    in one is terminal and the dir is older than ``max_age_days`` it is
    consumable. Unreadable journals are retained (unknown is not dead).
    """
    stamp = _now(now)
    removed: list[str] = []
    retained: list[str] = []
    if not root.is_dir():
        return {"removed": removed, "removed_count": 0, "retained": retained}
    for db in sorted(root.rglob("state.sqlite")):
        journal_dir = db.parent
        if _mtime(journal_dir) > stamp - max(0.0, max_age_days) * 86400:
            continue
        if _mtime(journal_dir) > stamp - grace:
            retained.append(str(journal_dir))
            continue
        if not is_quiet(journal_dir, now=stamp, grace=grace):
            retained.append(str(journal_dir))
            continue
        if _has_nonterminal_runs(db) is not False:
            retained.append(str(journal_dir))
            continue
        _remove(journal_dir, removed, note="terminal journal older than retention age")
    return {"removed": removed, "removed_count": len(removed), "retained": retained}


def prune_stale_root_artifacts(
    lokay_home: Path,
    *,
    max_age_days: float = DEFAULT_MAX_AGE_DAYS,
    now: float | None = None,
) -> dict[str, Any]:
    """Old archive dirs and cleanup logs in ``~/.lokay`` are consumable."""
    stamp = _now(now)
    removed: list[str] = []
    if not lokay_home.is_dir():
        return {"removed": removed, "removed_count": 0}
    cutoff = stamp - max(0.0, max_age_days) * 86400
    for entry in sorted(lokay_home.iterdir()):
        name = entry.name
        matched = name.startswith(_ROOT_ARCHIVE_PREFIXES) or (
            name.startswith("preflight-") and name.endswith(".log")
        )
        if not matched or _mtime(entry) > cutoff:
            continue
        _remove(entry, removed, note="archive older than retention age")
    return {"removed": removed, "removed_count": len(removed)}


def _eviction_candidates(
    lokay_home: Path,
    fala_root: Path,
    *,
    grace: float,
    stamp: float,
) -> list[tuple[float, Path, str]]:
    """Oldest-first consumable candidates: wrappers, dead journals, archives, logs."""
    candidates: list[tuple[float, Path, str]] = []
    for prefix in _WRAPPER_PREFIXES:
        for path in fala_root.glob(f"{prefix}-*"):
            if path.is_dir() and _mtime(path) <= stamp - grace:
                candidates.append((_mtime(path), path, "hard-cap wrapper trace"))
    for db in fala_root.rglob("state.sqlite"):
        journal_dir = db.parent
        if not is_quiet(journal_dir, now=stamp, grace=grace):
            continue
        if _has_nonterminal_runs(db) is not False:
            continue
        candidates.append((_mtime(journal_dir), journal_dir, "hard-cap terminal journal"))
    for entry in lokay_home.iterdir():
        if entry.name.startswith(_ROOT_ARCHIVE_PREFIXES):
            candidates.append((_mtime(entry), entry, "hard-cap archive"))
    logs = lokay_home / "logs"
    if logs.is_dir():
        for entry in logs.iterdir():
            candidates.append((_mtime(entry), entry, "hard-cap old error log (last resort)"))
    candidates.sort(key=lambda item: (item[0], str(item[1])))
    return candidates


def enforce_hard_cap(
    lokay_home: Path,
    *,
    cap_bytes: int = DEFAULT_HARD_CAP_BYTES,
    now: float | None = None,
    grace: float = LIVE_GRACE_SECONDS,
) -> dict[str, Any]:
    """Evict oldest consumable execution data until ``~/.lokay`` fits the cap.

    The cap is hygiene, not a scheduler: eviction is oldest-first across
    consumable classes. Protected state (state, digests, decisions,
    recovery, quarantine, health-lease, worktrees, repos) is never evicted
    here; ``logs/`` only as the final class.
    """
    stamp = _now(now)
    before = dir_size(lokay_home)
    removed: list[str] = []
    freed = 0
    if before <= max(0, int(cap_bytes)):
        return {"before_bytes": before, "after_bytes": before, "cap_bytes": int(cap_bytes),
                "removed": removed, "freed_bytes": 0, "over_cap": False}
    fala_root = lokay_home / "fala"
    candidates = _eviction_candidates(lokay_home, fala_root, grace=grace, stamp=stamp)
    for _mtime_, path, note in candidates:
        if before - freed <= int(cap_bytes):
            break
        size = dir_size(path)
        if _remove(path, removed, note=note):
            freed += size
    after = before - freed
    return {"before_bytes": before, "after_bytes": after, "cap_bytes": int(cap_bytes),
            "removed": removed, "freed_bytes": freed, "over_cap": after > int(cap_bytes)}


def apply_filesystem_retention(
    home: Path | None = None,
    *,
    max_age_days: float = DEFAULT_MAX_AGE_DAYS,
    hard_cap_bytes: int = DEFAULT_HARD_CAP_BYTES,
    wrapper_keep: int = DEFAULT_WRAPPER_KEEP,
    now: float | None = None,
) -> dict[str, Any]:
    """Run the filesystem half of the retention policy (no sqlite edits)."""
    root = (home or Path.home()) / ".lokay"
    fala_root = root / "fala"
    return {
        "wrapper_journals": prune_wrapper_journals(fala_root, keep=wrapper_keep, now=now),
        "stale_journal_dirs": prune_stale_journal_dirs(fala_root, max_age_days=max_age_days, now=now),
        "root_artifacts": prune_stale_root_artifacts(root, max_age_days=max_age_days, now=now),
        "hard_cap": enforce_hard_cap(root, cap_bytes=hard_cap_bytes, now=now),
    }
