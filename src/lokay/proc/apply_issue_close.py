"""Apply the CLOSE effect for one issue."""

from __future__ import annotations
from lokay.gh_issues import close_issue, comment_issue


def apply(*, runner, repo: str, issue: int, decision: dict, live: bool) -> dict:
    if not live:
        return {"ok": True, "planned": True, "verdict": "close"}
    comment_issue(
        runner,
        repo,
        issue,
        f"Closed (Lokay intake): {decision.get('reason') or 'agent_close'}.",
        live=True,
    )
    close_issue(runner, repo, issue, live=True)
    return {"ok": True, "applied": True, "verdict": "close"}
