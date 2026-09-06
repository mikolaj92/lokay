"""Park one issue by factory (no human route)."""

from __future__ import annotations
from lokay.gh_issues import add_issue_labels, comment_issue


def apply(*, runner, cfg, repo: str, issue: int, decision: dict, live: bool) -> dict:
    if not live:
        return {"ok": True, "planned": True, "verdict": "park"}
    reason = str(decision.get("reason") or "park")
    summary = str(decision.get("summary") or "").strip()
    note = f"Parked by factory (Lokay): {reason}."
    if summary:
        note = f"{note} {summary}."
    # Host-ops parks use ai:frozen (factory; zero needs_human).
    labels = [cfg.needs_feedback_label]
    if "host_ops" in reason.lower():
        labels = ["ai:frozen"]
    add_issue_labels(runner, repo, issue, labels, live=True)
    comment_issue(runner, repo, issue, note, live=True)
    return {"ok": True, "applied": True, "verdict": "park"}
