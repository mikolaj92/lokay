from __future__ import annotations

import logging
from pathlib import Path

from lokay.effects.gh import merge as gh_merge
from lokay.store import write_run
from lokay.main_guard import check_main


def merge_sha(repo_name: str, number: int, sha: str, verdict: dict, worktree: Path | None, held: dict | None, owner: str, issue: int, rounds: dict, *, clone_path: Path | None = None) -> dict:
    if verdict.get("result") != "merge" or verdict.get("sha") != sha:
        return {"result": "sha_moved", "merge_sha": None}
    if worktree is not None and clone_path is None:
        raise ValueError("clone_path is required to remove a worktree")
    outcome = gh_merge(repo_name, number, sha)
    if outcome["result"] != "merged":
        return outcome
    sha = outcome["merge_sha"]
    if clone_path is None:
        from lokay.config import load_repos

        clone_path = Path(next(row["clone_path"] for row in load_repos() if row["name"] == repo_name)).expanduser()
    check_main(repo_name, clone_path, sha, number)
    write_run(owner, repo_name, issue, {**rounds, "result": "merged", "sha": sha,
                                      "failures": 0, "retry_at": 0, "reason": None, "last_error": None})
    if worktree is not None:
        from lokay.tick import release_worktree
        from lokay.store import state_update

        state_update(repo_name, issue, cleanup_pending=True)
        removed = release_worktree({"name": repo_name, "clone_path": str(clone_path)}, issue, path=worktree)
        if removed["result"] != "released":
            logging.getLogger(__name__).warning("Merged %s#%s; worktree cleanup failed for %s: %s",
                                               repo_name, issue, worktree, removed["reason"])
    return {"result": "merged", "merge_sha": sha}
