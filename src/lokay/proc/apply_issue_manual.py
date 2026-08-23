"""Park one issue at the terminal human boundary."""

from __future__ import annotations
from lokay.gh_issues import add_issue_labels, comment_issue


def apply(*, runner, cfg, repo: str, issue: int, decision: dict, live: bool) -> dict:
    if not live:
        return {"ok": True, "planned": True, "verdict": "needs_human"}
    add_issue_labels(runner, repo, issue, [cfg.needs_feedback_label], live=True)
    comment_issue(
        runner,
        repo,
        issue,
        f"Needs feedback (Lokay intake): {decision.get('reason') or 'needs_human'}.",
        live=True,
    )
    return {"ok": True, "applied": True, "verdict": "needs_human"}
