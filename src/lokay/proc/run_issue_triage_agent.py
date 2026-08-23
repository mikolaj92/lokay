"""Run the initial semantic issue-triage agent call."""

from __future__ import annotations
from lokay.issue_triage_agent import prompt
from lokay.proc._issue_triage_agent_runtime import execute


def run(
    *,
    cfg,
    repo: str,
    issue: int,
    issue_data: dict,
    hard_facts: dict,
    clone_path,
    live: bool,
) -> dict:
    return execute(
        cfg=cfg,
        repo=repo,
        issue=issue,
        clone_path=clone_path,
        prompt=prompt(issue_data, hard_facts),
        live=live,
    )
