"""Invoke the authored local-test execution Fala."""

from pathlib import Path

from lokay.graph_run import run_path
from lokay.stuck import issue_number_from_branch


def _repo_of(worktree: str, repo: str | None) -> str:
    if repo:
        return str(repo)
    parent = Path(worktree).parent.name
    if "__" in parent:
        return parent.replace("__", "/", 1)
    return "local/test"


def _issue_of(worktree: str, issue: int | None) -> int | None:
    if issue is not None:
        try:
            number = int(issue)
        except (TypeError, ValueError):
            number = 0
        return number if number > 0 else None
    name = Path(worktree).name.replace("__", "/")
    return issue_number_from_branch(name)


def run(
    *,
    worktree: str,
    changed_scope: bool,
    repo: str | None = None,
    issue: int | None = None,
) -> dict:
    repo_id = _repo_of(worktree, repo)
    issue_number = _issue_of(worktree, issue)
    return run_path(
        path_id="test_local_execution",
        repo=repo_id,
        issue=issue_number,
        live=False,
        max_ticks=64,
        extra_inputs={
            "worktree": worktree,
            "changed_scope": changed_scope,
            "repo": repo_id,
            "issue": issue_number,
        },
    )
