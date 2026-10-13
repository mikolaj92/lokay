from __future__ import annotations

import logging
from pathlib import Path

from lokay.gh import merge as gh_merge
from lokay.git import worktree_remove
from lokay.state import write_run


def merge_sha(repo_name: str, number: int, sha: str, verdict: dict, worktree: Path | None, held: dict | None, owner: str, issue: int, rounds: dict, *, clone_path: Path | None = None) -> dict:
    if verdict.get("result") != "merge" or verdict.get("sha") != sha:
        return {"result": "sha_moved", "merge_sha": None}
    if worktree is not None and clone_path is None:
        raise ValueError("clone_path is required to remove a worktree")
    outcome = gh_merge(repo_name, number, sha)
    if outcome["result"] != "merged":
        return outcome
    write_run(owner, repo_name, issue, {**rounds, "result": "merged", "sha": sha,
                                      "failures": 0, "retry_at": 0, "reason": None, "last_error": None})
    if worktree is not None:
        try:
            removed = worktree_remove(clone_path, worktree)
            if removed["result"] != "removed":
                raise RuntimeError(removed.get("error") or "worktree removal failed")
        except Exception as exc:
            logging.getLogger(__name__).warning("Merged %s#%s; worktree cleanup failed for %s: %s",
                                               repo_name, issue, worktree, exc)
    # The run owner (start.main) releases the lock after all merge work.
    return {"result": "merged", "merge_sha": sha}
