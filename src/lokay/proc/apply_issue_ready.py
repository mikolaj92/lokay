"""Apply the READY effect for one issue."""

from __future__ import annotations
from lokay.gh_issues import WORK_READY_LABEL, add_issue_labels, assign_issue, remove_issue_labels
from lokay.proc.classify_issue_assignee import takeable


def apply(*, runner, cfg, repo: str, issue: int, issue_data: dict, live: bool) -> dict:
    if not live:
        return {"ok": True, "planned": True, "verdict": "ready"}
    have = set(issue_data.get("labels") or [])
    human = str(getattr(cfg, "needs_feedback_label", None) or "ai:needs-feedback")
    blocked = str(getattr(cfg, "blocked_label", None) or "ai:blocked")
    stale = [label for label in (human, blocked) if label and label in have]
    if stale:
        remove_issue_labels(runner, repo, issue, stale, live=True)
        have -= set(stale)
    labels = [x for x in (cfg.ready_label, WORK_READY_LABEL) if x not in have]
    if labels:
        add_issue_labels(runner, repo, issue, labels, live=True)
    assignees = list(issue_data.get("assignees") or [])
    if (
        cfg.assignee
        and takeable({"assignees": assignees}, cfg.assignee)
        and cfg.assignee not in assignees
    ):
        assign_issue(runner, cfg, repo, issue, live=True)
    return {"ok": True, "applied": True, "verdict": "ready"}
