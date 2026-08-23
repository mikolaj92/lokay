"""Run one issue-triage retry with exact validator feedback."""

from __future__ import annotations
from lokay.issue_triage_agent import prompt
from lokay.proc._issue_triage_agent_runtime import execute
from lokay.review_boundary import validation_feedback_prompt


def run(
    *,
    cfg,
    repo: str,
    issue: int,
    issue_data: dict,
    hard_facts: dict,
    feedback: dict,
    clone_path,
    live: bool,
) -> dict:
    text = (
        prompt(issue_data, hard_facts)
        + "\n\n"
        + validation_feedback_prompt(
            str(feedback.get("validation_error") or "invalid output"),
            str(feedback.get("agent_stdout_tail") or ""),
        )
    )
    return execute(
        cfg=cfg, repo=repo, issue=issue, clone_path=clone_path, prompt=text, live=live
    )
