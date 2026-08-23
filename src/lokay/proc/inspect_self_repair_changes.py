"""Read uncommitted class, HEAD, and exact ahead count for an owned worktree."""

from pathlib import Path
from lokay.git_real_diff import classify_changed_paths, list_uncommitted_paths
from lokay.proc._common import runner
from lokay.runner import git_spec


def inspect(owned: dict) -> dict:
    run = runner()
    worktree = Path(owned["worktree"])
    uncommitted = classify_changed_paths(list_uncommitted_paths(run, worktree))
    head = run.run_checked(
        git_spec(["rev-parse", "HEAD"], cwd=worktree, timeout_seconds=60), live=True
    ).stdout.strip()
    text = run.run_checked(
        git_spec(
            ["rev-list", "--count", f"{owned['base_sha']}..HEAD"],
            cwd=worktree,
            timeout_seconds=60,
        ),
        live=True,
    ).stdout.strip()
    try:
        ahead = int(text)
        return {
            **owned,
            "route": "changes",
            "uncommitted": uncommitted,
            "head": head,
            "ahead": ahead,
        }
    except ValueError:
        return {
            **owned,
            "route": "error",
            "error": f"cannot parse existing self-repair ahead count: {text!r}",
        }
