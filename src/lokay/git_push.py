from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from lokay.git_commit import is_configured_issue_worktree
from lokay.runner import Runner, git_spec


def is_configured_issue_branch(
    runner: Runner,
    worktree: Path,
    branch: str,
    configured_checkouts: Iterable[Path],
) -> bool:
    """Whether an issue worktree has exactly *branch* checked out."""
    if not is_configured_issue_worktree(runner, worktree, configured_checkouts):
        return False
    current = runner.run(
        git_spec(["symbolic-ref", "--quiet", "--short", "HEAD"], cwd=worktree),
        live=True,
    )
    return current.returncode == 0 and (current.stdout or "").strip() == branch


def push_branch(runner: Runner, worktree: Path, branch: str, *, live: bool) -> None:
    """Push only. Force flags are rejected by safety.validate_argv."""
    runner.run_checked(
        git_spec(["push", "-u", "origin", branch], cwd=worktree, timeout_seconds=300),
        live=live,
    )
