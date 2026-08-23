"""Apply the READY effect for one issue."""

from __future__ import annotations
from lokay.gh_issues import WORK_READY_LABEL, add_issue_labels, assign_issue


def apply(*, runner, cfg, repo: str, issue: int, issue_data: dict, live: bool) -> dict:
    if not live:
        return {"ok": True, "planned": True, "verdict": "ready"}
    have = set(issue_data.get("labels") or [])
    labels = [x for x in (cfg.ready_label, WORK_READY_LABEL) if x not in have]
    if labels:
        add_issue_labels(runner, repo, issue, labels, live=True)
    if cfg.assignee and cfg.assignee not in (issue_data.get("assignees") or []):
        assign_issue(runner, cfg, repo, issue, live=True)
    return {"ok": True, "applied": True, "verdict": "ready"}
