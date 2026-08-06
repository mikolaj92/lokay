from __future__ import annotations

from pathlib import Path

from lokay.runner import Runner, git_spec


def push_branch(runner: Runner, worktree: Path, branch: str, *, live: bool) -> None:
    """Push only. Force flags are rejected by safety.validate_argv."""
    runner.run_checked(
        git_spec(["push", "-u", "origin", branch], cwd=worktree, timeout_seconds=300),
        live=live,
    )
