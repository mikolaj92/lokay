"""Apply the physical BLOCKED label for one carrier incident issue."""

from __future__ import annotations
from lokay.gh_issues import add_issue_labels, remove_issue_labels


def apply(*, runner, cfg, repo: str, issue: int, issue_data: dict, live: bool) -> dict:
    if not live:
        return {"ok": True, "planned": True, "verdict": "blocked"}
    have = set(issue_data.get("labels") or [])
    remove = [label for label in (cfg.ready_label, "work:ready") if label in have]
    if remove:
        remove_issue_labels(runner, repo, issue, remove, live=True)
    if cfg.blocked_label not in have:
        add_issue_labels(runner, repo, issue, [cfg.blocked_label], live=True)
    return {"ok": True, "applied": True, "verdict": "blocked"}
