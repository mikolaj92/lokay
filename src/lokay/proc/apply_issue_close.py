"""Apply the CLOSE effect for one issue.

Intake/sito may decide close. This atom must not close a still-open
product issue. Already-closed issues are the only exception.
"""

from __future__ import annotations
from lokay.gh_issues import close_issue, comment_issue


def apply(
    *,
    runner,
    repo: str,
    issue: int,
    decision: dict,
    live: bool,
    issue_data: dict | None = None,
) -> dict:
    state = str((issue_data or {}).get("state") or "OPEN").strip().upper()
    if state != "CLOSED":
        return {
            "ok": True,
            "planned": True,
            "refused": True,
            "applied": False,
            "verdict": "close",
            "reason": "still_open",
        }
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
