"""Invoke authored deterministic issue-planning Fala."""

from lokay.approach_plan import APPROACH_REL_PATH
from lokay.graph_run import run_path


def run(
    *,
    config_path: str | None,
    live: bool,
    worktree: str,
    issue_raw: dict | None = None,
    repo: str = "",
    issue: int | None = None,
    title: str = "",
    body: str = "",
    url: str = "",
    rel_path: str = APPROACH_REL_PATH,
) -> dict:
    return run_path(
        path_id="plan_issue_execution",
        repo=repo or str((issue_raw or {}).get("repo") or "local/plan"),
        issue=issue,
        config_path=config_path,
        live=live,
        max_ticks=32,
        extra_inputs={
            "config_path": config_path or "",
            "live": live,
            "worktree": worktree,
            "issue_raw": issue_raw or {},
            "repo": repo,
            "issue": issue,
            "title": title,
            "body": body,
            "url": url,
            "rel_path": rel_path,
        },
    )
