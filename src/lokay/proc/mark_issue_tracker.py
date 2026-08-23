"""Replace parent work labels with the tracker label."""

from __future__ import annotations
from lokay.gh_issues import add_issue_labels, remove_issue_labels


def apply(
    *, runner, cfg, repo: str, issue: int, issue_data: dict, plan: dict, live: bool
) -> dict:
    if not live:
        return {"ok": True, "planned": True}
    have = set(issue_data.get("labels") or [])
    remove = [x for x in (cfg.ready_label, cfg.needs_feedback_label) if x in have]
    if remove:
        remove_issue_labels(runner, repo, issue, remove, live=True)
    add_issue_labels(
        runner,
        repo,
        issue,
        [str(plan.get("parent_tracker_label") or "ai:tracker")],
        live=True,
    )
    return {"ok": True, "applied": True}
