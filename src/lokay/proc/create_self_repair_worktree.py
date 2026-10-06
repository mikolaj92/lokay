"""Create one detached recovery worktree from the exact fetched base."""

from pathlib import Path

from lokay.proc._common import runner
from lokay.git_worktree import prepare_worktree_parent
from lokay.runner import git_spec


def create(route: dict) -> dict:
    worktree = Path(route["worktree"])
    prepare_worktree_parent(worktree)
    runner().run_checked(
        git_spec(
            ["worktree", "add", "--detach", str(worktree), route["base_sha"]],
            cwd=Path(route["clone"]),
        ),
        live=True,
    )
    return {**route, "ok": True, "route": "created"}
