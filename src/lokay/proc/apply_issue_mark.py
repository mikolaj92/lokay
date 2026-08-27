"""Park a sito close verdict. Label and comment; never close the issue."""

from __future__ import annotations
from lokay.gh_issues import add_issue_labels, comment_issue, remove_issue_labels


def apply(*, runner, cfg, repo: str, issue: int, issue_data: dict, decision: dict, live: bool) -> dict:
    reason = str(decision.get("reason") or "sito_mark")
    if not live:
        return {"ok": True, "planned": True, "verdict": "close", "marked": True, "reason": reason}
    have = set(issue_data.get("labels") or [])
    remove = [label for label in (cfg.ready_label, "work:ready") if label in have]
    if remove:
        remove_issue_labels(runner, repo, issue, remove, live=True)
    if cfg.blocked_label not in have:
        add_issue_labels(runner, repo, issue, [cfg.blocked_label], live=True)
    comment_issue(
        runner,
        repo,
        issue,
        f"Parked (Lokay intake): {reason}.",
        live=True,
    )
    return {"ok": True, "applied": True, "verdict": "close", "marked": True, "reason": reason}
