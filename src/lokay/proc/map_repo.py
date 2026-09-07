"""Map one checkout before triage or coding. Empty when ripwire is absent."""

from __future__ import annotations

from lokay.ripwire import ranked_paths, repo_map, task_from_issue


def map_repo(
    *,
    worktree: str = "",
    title: str = "",
    body: str = "",
) -> dict:
    task = task_from_issue(title, body)
    text = repo_map(worktree, task=task)
    paths = list(ranked_paths(worktree, task=task, raw=text))
    return {
        "ok": True,
        "route": "mapped" if text else "empty",
        "map": text,
        "paths": paths,
        "source": "ripwire" if text else "missing",
    }
