from __future__ import annotations

from pathlib import Path

from lokay.config import Config, RepoConfig
from lokay.runner import Runner, git_spec


class InvalidBranchRef(ValueError):
    """Git will not accept this as ``refs/heads/*`` (e.g. a ``..`` slug)."""

    def __init__(self, branch: str, detail: str = "") -> None:
        self.branch = branch
        self.reason = "invalid_branch_ref"
        msg = f"invalid branch ref: {branch}"
        if detail:
            msg = f"{msg}: {detail}"
        super().__init__(msg)


def assert_valid_branch_ref(
    runner: Runner,
    branch: str,
    *,
    cwd: Path | None = None,
) -> None:
    """Fail closed before ``git worktree add`` if the head is not a legal ref."""
    result = runner.run(
        git_spec(
            ["check-ref-format", "--normalize", f"refs/heads/{branch}"],
            cwd=cwd,
            timeout_seconds=30,
        ),
        live=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise InvalidBranchRef(branch, detail)


def ensure_worktree(
    runner: Runner,
    config: Config,
    repo: RepoConfig,
    branch: str,
    *,
    live: bool,
    base: str = "main",
    reset_to_base: bool = False,
) -> Path:
    """Ensure a worktree for *branch*.

    When ``reset_to_base`` is True (issue_to_pr re-implement path):

    * KEEP if the existing corner is ahead of ``origin/<base>`` (unpublished
      commits). Restart must not wipe a child that has not published a PR.
    * RESET (``-B`` from ``origin/<base>`` + best-effort remote delete) only
      when ahead is 0 — conflict rewrite after the corner is already empty
      or already aligned with base.
    * Fail closed if ahead cannot be measured. Do not ``rm -rf``.
    """
    root = config.worktrees_root / repo.name.replace("/", "__")
    worktree = root / branch.replace("/", "__")
    if not live:
        return worktree

    clone = repo.clone_path
    assert_valid_branch_ref(runner, branch, cwd=clone if Path(clone).exists() else None)

    root.mkdir(parents=True, exist_ok=True)
    runner.run_checked(
        git_spec(["fetch", "origin", base], cwd=clone, timeout_seconds=300),
        live=True,
    )
    start_ref = f"origin/{base}"

    if reset_to_base:
        if worktree.exists():
            ahead_result = runner.run(
                git_spec(
                    ["rev-list", "--count", f"origin/{base}..HEAD"],
                    cwd=worktree,
                    timeout_seconds=60,
                ),
                live=True,
            )
            if ahead_result.returncode != 0:
                detail = (ahead_result.stderr or ahead_result.stdout or "").strip()
                raise RuntimeError(
                    f"cannot measure unpublished ahead vs origin/{base}: {detail}"
                )
            try:
                ahead = int((ahead_result.stdout or "").strip())
            except ValueError as exc:
                raise RuntimeError(
                    f"cannot measure unpublished ahead vs origin/{base}: "
                    f"{(ahead_result.stdout or '').strip()!r}"
                ) from exc
            if ahead > 0:
                return worktree
            rm = runner.run(
                git_spec(
                    ["worktree", "remove", "--force", str(worktree)],
                    cwd=clone,
                    timeout_seconds=120,
                ),
                live=True,
            )
            if rm.returncode != 0 and worktree.exists():
                # Detached/corrupt registry: drop directory then prune.
                import shutil

                shutil.rmtree(worktree, ignore_errors=True)
                runner.run(
                    git_spec(["worktree", "prune"], cwd=clone, timeout_seconds=60),
                    live=True,
                )
        # -B: create or reset branch to start_ref at the new worktree path.
        result = runner.run(
            git_spec(
                ["worktree", "add", "-B", branch, str(worktree), start_ref],
                cwd=clone,
                timeout_seconds=180,
            ),
            live=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"worktree reset-to-base failed:\n{result.stderr}\n{result.stdout}"
            )
        # Drop stale remote tip (old conflicting commits) so push need not force.
        runner.run(
            git_spec(
                ["push", "origin", "--delete", branch],
                cwd=clone,
                timeout_seconds=120,
            ),
            live=True,
        )
        return worktree

    if worktree.exists():
        return worktree

    result = runner.run(
        git_spec(
            ["worktree", "add", "-b", branch, str(worktree), start_ref],
            cwd=clone,
            timeout_seconds=180,
        ),
        live=True,
    )
    if result.returncode != 0:
        result2 = runner.run(
            git_spec(["worktree", "add", str(worktree), branch], cwd=clone, timeout_seconds=180),
            live=True,
        )
        if result2.returncode != 0:
            result3 = runner.run(
                git_spec(
                    [
                        "worktree",
                        "add",
                        "--track",
                        "-b",
                        branch,
                        str(worktree),
                        f"origin/{branch}",
                    ],
                    cwd=clone,
                    timeout_seconds=180,
                ),
                live=True,
            )
            if result3.returncode != 0:
                raise RuntimeError(
                    "worktree add failed:\n"
                    f"{result.stderr}\n{result2.stderr}\n{result3.stderr}"
                )
    return worktree
