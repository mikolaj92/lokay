"""Park a preflight/blocked leaf as a machine stop (ai:frozen)."""

from __future__ import annotations

from lokay.gh_issues import add_issue_labels, remove_issue_labels
from lokay.triage import MACHINE_PARK_LABEL


def apply(*, runner, cfg, repo: str, issue: int, issue_data: dict, live: bool) -> dict:
    if not live:
        return {"ok": True, "planned": True, "verdict": "blocked"}
    have = set(issue_data.get("labels") or [])
    human = str(getattr(cfg, "needs_feedback_label", None) or "ai:needs-feedback")
    blocked = str(getattr(cfg, "blocked_label", None) or "ai:blocked")
    remove = [
        label
        for label in (cfg.ready_label, "work:ready", human, blocked)
        if label and label in have and label != MACHINE_PARK_LABEL
    ]
    if remove:
        remove_issue_labels(runner, repo, issue, remove, live=True)
    if MACHINE_PARK_LABEL not in have:
        add_issue_labels(runner, repo, issue, [MACHINE_PARK_LABEL], live=True)
    return {
        "ok": True,
        "applied": True,
        "verdict": "blocked",
        "labels": [MACHINE_PARK_LABEL],
    }
