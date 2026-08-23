"""Run the authored issue-split Fala subflow from an issue-triage verdict."""

from __future__ import annotations
from lokay.proc.issue_split import run


def invoke(
    *, config_path: str | None, repo: str, issue: int, decision: dict, live: bool
) -> dict:
    return run(
        config_path=config_path,
        repo=repo,
        issue=issue,
        reason=str(decision.get("reason") or "agent_split"),
        live=live,
    )
