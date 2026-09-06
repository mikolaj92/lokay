"""Park one issue by factory (no human route)."""

from __future__ import annotations
from lokay.gh_issues import add_issue_labels, comment_issue


def apply(*, runner, cfg, repo: str, issue: int, decision: dict, live: bool) -> dict:
    if not live:
        return {"ok": True, "planned": True, "verdict": "park"}
    add_issue_labels(runner, repo, issue, [cfg.needs_feedback_label], live=True)
    comment_issue(
        runner,
        repo,
        issue,
        f"Parked by factory (Lokay): {decision.get('reason') or 'park'}.",
        live=True,
    )
    return {"ok": True, "applied": True, "verdict": "park"}
