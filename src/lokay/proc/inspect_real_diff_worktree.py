"""Validate one physical worktree location."""

from pathlib import Path


def inspect(*, worktree: str) -> dict:
    root = Path(worktree).resolve()
    return {
        "ok": True,
        "route": "read" if root.is_dir() else "terminal",
        "reason": "" if root.is_dir() else "invalid_worktree",
        "worktree": str(root),
    }
