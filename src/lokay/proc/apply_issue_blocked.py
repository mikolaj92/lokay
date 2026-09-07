"""Skip a preflight/blocked leaf — strip ready, never stamp limbo labels."""

from __future__ import annotations

from lokay.gh_issues import remove_issue_labels
from lokay.triage import LIMBO_LABELS


def apply(*, runner, cfg, repo: str, issue: int, issue_data: dict, live: bool) -> dict:
    if not live:
        return {"ok": True, "planned": True, "verdict": "skip", "labels": []}
    have = set(issue_data.get("labels") or [])
    human = str(getattr(cfg, "needs_feedback_label", None) or "ai:needs-feedback")
    blocked = str(getattr(cfg, "blocked_label", None) or "ai:blocked")
    remove = [
        label
        for label in (cfg.ready_label, "work:ready", human, blocked, *LIMBO_LABELS)
        if label and label in have
    ]
    # de-dupe preserve order
    seen: set[str] = set()
    ordered = []
    for label in remove:
        if label not in seen:
            seen.add(label)
            ordered.append(label)
    if ordered:
        remove_issue_labels(runner, repo, issue, ordered, live=True)
    return {
        "ok": True,
        "applied": True,
        "verdict": "skip",
        "labels": [],
        "skipped": True,
        "reason": "preflight_incident",
    }
