from __future__ import annotations

from pathlib import Path

from lokay.config import Config, RepoConfig
from lokay.runner import Runner, git_spec


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

    When ``reset_to_base`` is True (issue_to_pr re-implement path), the worktree
    and branch are recreated from ``origin/<base>`` so a prior CONFLICTING PR on
    the same branch name cannot poison the next attempt. Best-effort deletes the
    remote branch so a subsequent non-force push can publish the rewrite.
    """
    root = config.worktrees_root / repo.name.replace("/", "__")
    worktree = root / branch.replace("/", "__")
    if not live:
        return worktree

    root.mkdir(parents=True, exist_ok=True)
    clone = repo.clone_path
    runner.run_checked(
        git_spec(["fetch", "origin", base], cwd=clone, timeout_seconds=300),
        live=True,
    )
    start_ref = f"origin/{base}"

    if reset_to_base:
        if worktree.exists():
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
