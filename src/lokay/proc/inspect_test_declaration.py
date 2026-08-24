"""Inspect one repository-declared local test command."""

from pathlib import Path
from lokay.proc.test_local import declared_test_argv


def inspect(*, worktree: str) -> dict:
    root = Path(worktree).resolve()
    if not root.is_dir():
        return {
            "ok": True,
            "route": "terminal",
            "result": {
                "ok": False,
                "error": "worktree is not a directory",
                "worktree": str(root),
            },
        }
    try:
        argv = declared_test_argv(root)
    except ValueError as exc:
        return {
            "ok": True,
            "route": "terminal",
            "result": {
                "ok": False,
                "error": str(exc),
                "reason": "invalid_test_declaration",
                "tested": False,
                "worktree": str(root),
            },
        }
    if not argv:
        return {
            "ok": True,
            "route": "terminal",
            "result": {
                "ok": True,
                "skipped": True,
                "reason": "no_declared_test",
                "tested": False,
                "worktree": str(root),
            },
        }
    return {"ok": True, "route": "test", "worktree": str(root), "test_argv": list(argv)}
