"""Inspect one optional product-verify command.

`[tool.lokay] verify` is a second contract, not a stand-in for the declared
test. Missing means an honest skip. A bad value fails closed. Nothing here
invents a harness.
"""

from pathlib import Path

from lokay.proc.test_local import declared_argv


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
        argv = declared_argv(root, "verify")
    except ValueError as exc:
        return {
            "ok": True,
            "route": "terminal",
            "result": {
                "ok": False,
                "error": str(exc),
                "reason": "invalid_verify_declaration",
                "verified": False,
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
                "reason": "no_declared_verify",
                "verified": False,
                "worktree": str(root),
            },
        }
    return {"ok": True, "route": "verify", "worktree": str(root), "verify_argv": list(argv)}
