"""Apply the CLOSE effect for one issue.

Sito must not close a foreign issue. Refuse obsolete_* fail-closed.
Refuse every still-open issue (no comment, no close). Already-closed
issues are the only remaining exception, and never for obsolete_*.
"""

from __future__ import annotations
from lokay.gh_issues import close_issue, comment_issue


def obsolete_close_reason(reason: object) -> bool:
    return str(reason or "").startswith("obsolete_")


def apply(
    *,
    runner,
    repo: str,
    issue: int,
    decision: dict,
    live: bool,
    issue_data: dict | None = None,
) -> dict:
    reason = str(decision.get("reason") or "agent_close")
    if obsolete_close_reason(reason):
        return {
            "ok": False,
            "error": "sito_must_not_close_obsolete",
            "reason": reason,
            "verdict": "close",
            "closed": False,
            "refused": True,
            "applied": False,
        }
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
        f"Closed (Lokay intake): {reason}.",
        live=True,
    )
    close_issue(runner, repo, issue, live=True)
    return {"ok": True, "applied": True, "verdict": "close"}
