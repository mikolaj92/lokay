from __future__ import annotations

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
    if worktree is not None:
        removed = worktree_remove(clone_path, worktree)
        if removed["result"] != "removed":
            raise RuntimeError(removed.get("error") or "worktree removal failed")
    # The run owner (start.main) releases the lock after all merge work.
    write_run(owner, repo_name, issue, rounds)
    return {"result": "merged", "merge_sha": sha}
