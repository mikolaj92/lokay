from __future__ import annotations

from pathlib import Path

from lokay2.gh import merge as gh_merge
from lokay2.git import worktree_remove
from lokay2.lock import release
from lokay2.state import write_run


def merge_sha(repo_name: str, number: int, sha: str, verdict: dict, worktree: Path | None, held: dict | None, owner: str, issue: int, rounds: dict) -> dict:
    if verdict.get("result") != "merge" or verdict.get("sha") != sha:
        return {"result": "sha_moved", "merge_sha": None}
    outcome = gh_merge(repo_name, number, sha)
    if outcome["result"] != "merged":
        return outcome
    if worktree is not None:
        worktree_remove(worktree.parent if worktree.parent.name != "" else worktree, worktree)
    if held is not None:
        release(held)
    write_run(owner, repo_name, issue, rounds)
    return {"result": "merged", "merge_sha": sha}
