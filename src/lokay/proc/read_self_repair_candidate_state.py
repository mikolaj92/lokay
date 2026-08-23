"""Read initial tracked status and committed path class for a recovery candidate."""

from pathlib import Path
from lokay.git_real_diff import classify_changed_paths, list_committed_paths
from lokay.proc._common import runner
from lokay.runner import git_spec


def read(*, worktree: str, base_sha: str) -> dict:
    path = Path(worktree).resolve()
    run = runner()
    changed = run.run_checked(
        git_spec(["status", "--porcelain"], cwd=path), live=True
    ).stdout.strip()
    paths = list_committed_paths(run, path, base=base_sha) if base_sha else []
    return {
        "ok": True,
        "worktree": str(path),
        "base_sha": base_sha,
        "changed": changed,
        "committed": classify_changed_paths(paths),
    }
