"""List dirty Done-means stamp paths in one worktree (ok|fail structured)."""

from __future__ import annotations

from pathlib import Path

from lokay.runner import Runner, git_spec
from lokay.stamp_paths import dirty_stamp_paths


def list_paths(worktree: str | Path, *, live: bool = True) -> dict:
    root = Path(worktree)
    if not live:
        return {"ok": True, "route": "clean", "dirty_stamps": [], "planned": True}
    runner = Runner()
    porcelain = runner.run(
        git_spec(["status", "--porcelain", "-u"], cwd=root), live=True
    ).stdout
    dirty = dirty_stamp_paths(root, porcelain=porcelain)
    return {
        "ok": True,
        "route": "dirty" if dirty else "clean",
        "dirty_stamps": dirty,
        "planned": False,
    }
