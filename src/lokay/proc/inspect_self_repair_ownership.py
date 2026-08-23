"""Read exact ownership of one existing recovery worktree."""

from pathlib import Path
from lokay.git_worktree import worktree_owned_by_clone
from lokay.proc._common import runner


def inspect(base: dict) -> dict:
    owned = worktree_owned_by_clone(
        runner(), Path(base["clone"]), Path(base["worktree"])
    )
    return {
        **base,
        "route": "owned" if owned is True else "error",
        "owned": owned,
        "error": (
            ""
            if owned is True
            else (
                "cannot resume existing self-repair worktree: unreadable"
                if owned is None
                else "cannot resume existing self-repair worktree: not owned by canonical clone"
            )
        ),
    }
