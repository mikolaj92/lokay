"""Read subject and committed-path class for one clean ahead candidate."""

from pathlib import Path
from lokay.git_real_diff import classify_changed_paths, list_committed_paths
from lokay.proc._common import runner
from lokay.runner import git_spec


def inspect(shape: dict) -> dict:
    run = runner()
    worktree = Path(shape["worktree"])
    subject = run.run_checked(
        git_spec(["log", "-1", "--format=%s"], cwd=worktree), live=True
    ).stdout.strip()
    committed = classify_changed_paths(
        list_committed_paths(run, worktree, base=shape["base_sha"])
    )
    return {**shape, "route": "commit", "subject": subject, "committed": committed}
