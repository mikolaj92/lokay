from __future__ import annotations

import logging
from pathlib import Path

from lokay.effects.gh import merge as gh_merge, pr_files
from lokay.effects.git import base_branch, worktree_remove
from lokay.graph import merge_allowed
from lokay.store import state_read, state_update
from lokay.main_guard import check_main


def merge_blocked(state: dict, sha: str) -> bool:
    return state.get("merge_conflict_sha") == sha or state.get("merge_attempts", {}).get(sha, 0) >= 2


def merge_sha(repo_name: str, number: int, sha: str, verdict: dict | None, worktree: Path | None, owner: str, issue: int, rounds: dict, *, clone_path: Path | None = None) -> dict:
    from lokay.review import recompute_verdict

    saved = state_read(repo_name, issue)
    if not merge_allowed(saved, sha) or (verdict := recompute_verdict(sha, saved)) is None:
        state_update(repo_name, issue, _event={"action": "enter_node", "outcome": {"node": "check"}},
                     sha=sha, verdict=None, result="check")
        return {"result": "check", "sha": sha, "merge_sha": None}
    if verdict.get("result") != "merge" or verdict.get("sha") != sha:
        return {"result": "sha_moved", "merge_sha": None}
    if worktree is not None and clone_path is None:
        raise ValueError("clone_path is required to remove a worktree")
    attempts = state_read(repo_name, issue).get("merge_attempts", {})
    if attempts.get(sha, 0) >= 2:
        state_update(repo_name, issue, merge_conflict_sha=sha)
        return {"result": "merge_limit", "merge_sha": None}
    if not pr_files(repo_name, number):
        state_update(repo_name, issue, result="closed", reason="empty PR diff")
        return {"result": "closed", "merge_sha": None, "reason": "empty PR diff"}
    base_path = worktree if worktree is not None else clone_path
    base = base_branch(base_path) if base_path is not None else None
    state_update(repo_name, issue, merge_attempts={**attempts, sha: attempts.get(sha, 0) + 1})
    outcome = gh_merge(repo_name, number, sha)
    if outcome["result"] == "conflict":
        state_update(repo_name, issue, merge_conflict_sha=sha)
    if outcome["result"] != "merged":
        return outcome
    sha = outcome["merge_sha"]
    if clone_path is None:
        from lokay.config import repo

        clone_path = Path(repo(repo_name)["clone_path"]).expanduser()
    check_main(repo_name, clone_path, sha, number, base=base)
    state_update(repo_name if "/" in repo_name else f"{owner}/{repo_name}", issue, **{**rounds, "result": "merged", "sha": sha,
                                      "failures": 0, "retry_at": 0, "reason": None, "last_error": None})
    if worktree is not None:
        try:
            removed = worktree_remove(clone_path, worktree)
            if removed["result"] != "removed":
                raise RuntimeError(removed.get("error") or "worktree removal failed")
        except Exception as exc:
            logging.getLogger(__name__).warning("Merged %s#%s; worktree cleanup failed for %s: %s",
                                               repo_name, issue, worktree, exc)
    return {"result": "merged", "merge_sha": sha}
