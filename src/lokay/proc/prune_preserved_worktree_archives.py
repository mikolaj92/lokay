"""One job: prune old `.lokay-preserved` archives under the managed worktree root.

Never touches Fala sqlite/WAL. Never walks outside managed_root. Tests must
pass a tmp managed_root — never the operator lokay root by accident.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from lokay.git_worktree import _is_quarantine_name, reclaim_preserved_archive
from lokay.proc.stale_worktree_catalog import SLOTS as ARCHIVE_GC_SLOTS

# Disk crisis on Temida leftovers: one hour is enough for operator recovery.
PRESERVED_ARCHIVE_TTL_SECONDS = 3600

def _is_operator_lokay_worktrees(root: Path) -> bool:
    lokay = Path.home() / ".lokay" / "worktrees"
    try:
        return root.expanduser().resolve() == lokay.resolve()
    except OSError:
        return Path(root).expanduser() == lokay


def _archive_age_seconds(path: Path, *, now: float) -> float | None:
    try:
        return now - path.lstat().st_mtime
    except OSError:
        return None


def list_expired_archives(
    managed_root: Path, *, now: float | None = None, ttl: int | None = None
) -> list[Path]:
    """Lexical children named `.*.lokay-preserved` older than TTL."""
    limit = PRESERVED_ARCHIVE_TTL_SECONDS if ttl is None else ttl
    stamp = time.time() if now is None else now
    if not managed_root.exists():
        return []
    found: list[Path] = []
    try:
        repo_dirs = sorted(managed_root.iterdir(), key=lambda p: p.name)
    except OSError:
        return []
    for repo_dir in repo_dirs:
        if not repo_dir.is_dir() or repo_dir.is_symlink():
            continue
        try:
            children = sorted(repo_dir.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for child in children:
            if child.is_symlink() or not child.is_dir():
                continue
            if not _is_quarantine_name(child.name):
                continue
            age = _archive_age_seconds(child, now=stamp)
            if age is None or age < limit:
                continue
            found.append(child)
    return found[:ARCHIVE_GC_SLOTS]


def prune(
    *,
    managed_root: Path,
    live: bool,
    now: float | None = None,
    ttl: int | None = None,
) -> dict[str, Any]:
    """Reclaim expired `.lokay-preserved` archives. Dry-run when live is false."""
    root = Path(managed_root).expanduser()
    limit = PRESERVED_ARCHIVE_TTL_SECONDS if ttl is None else ttl
    if os.environ.get("PYTEST_CURRENT_TEST") and _is_operator_lokay_worktrees(root):
        return {
            "ok": True,
            "skipped": True,
            "reason": "pytest_refuses_operator_lokay",
            "pruned": [],
            "pruned_count": 0,
            "ttl_seconds": limit,
        }
    expired = list_expired_archives(root, now=now, ttl=limit)
    if not live:
        return {
            "ok": True,
            "planned": True,
            "pruned": [],
            "candidates": [str(p) for p in expired],
            "pruned_count": 0,
            "candidate_count": len(expired),
            "ttl_seconds": limit,
        }
    pruned: list[str] = []
    failed: list[dict[str, str]] = []
    for path in expired:
        out = reclaim_preserved_archive(path, managed_root=root)
        if out.get("ok") and (out.get("reclaimed") or out.get("already_gone")):
            pruned.append(str(path))
        else:
            failed.append(
                {
                    "path": str(path),
                    "error": str(out.get("error") or "reclaim_failed"),
                }
            )
    return {
        "ok": True,
        "planned": False,
        "pruned": pruned,
        "failed": failed,
        "pruned_count": len(pruned),
        "failed_count": len(failed),
        "ttl_seconds": limit,
    }
