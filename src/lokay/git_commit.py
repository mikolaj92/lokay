from __future__ import annotations

from pathlib import Path

from lokay.runner import Runner, git_spec


def worktree_has_diff(runner: Runner, worktree: Path, *, live: bool) -> bool:
    if not live:
        return False
    staged = runner.run(git_spec(["diff", "--cached", "--quiet"], cwd=worktree), live=True)
    unstaged = runner.run(git_spec(["diff", "--quiet"], cwd=worktree), live=True)
    untracked = runner.run(
        git_spec(["ls-files", "--others", "--exclude-standard"], cwd=worktree),
        live=True,
    )
    return staged.returncode != 0 or unstaged.returncode != 0 or bool((untracked.stdout or "").strip())


def branch_ahead_of_main(
    runner: Runner, worktree: Path, *, live: bool, base: str = "main"
) -> int:
    if not live:
        return 0
    ahead = runner.run(
        git_spec(["rev-list", "--count", f"origin/{base}..HEAD"], cwd=worktree),
        live=True,
    )
    try:
        return int((ahead.stdout or "0").strip() or "0")
    except ValueError:
        return 0


def branch_ahead_of_upstream(runner: Runner, worktree: Path, *, live: bool) -> int:
    if not live:
        return 0
    ahead = runner.run(
        git_spec(["rev-list", "--count", "@{upstream}..HEAD"], cwd=worktree),
        live=True,
    )
    if ahead.returncode != 0:
        return 0
    try:
        return int((ahead.stdout or "0").strip() or "0")
    except ValueError:
        return 0


def commit_all(runner: Runner, worktree: Path, message: str, *, live: bool) -> bool:
    if not live:
        return False
    runner.run_checked(git_spec(["add", "-A"], cwd=worktree), live=True)
    status = runner.run(git_spec(["diff", "--cached", "--quiet"], cwd=worktree), live=True)
    if status.returncode == 0:
        return False
    runner.run_checked(git_spec(["commit", "-m", message], cwd=worktree), live=True)
    return True
