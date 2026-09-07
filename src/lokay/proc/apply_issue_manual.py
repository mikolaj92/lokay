"""Park one issue by factory (machine stop; never human mailbox)."""

from __future__ import annotations

from lokay.gh_issues import add_issue_labels, comment_issue
from lokay.proc.select_park_stop import MACHINE_PARK_LABEL


def apply(
    *,
    runner,
    cfg,
    repo: str,
    issue: int,
    decision: dict,
    live: bool,
    park_stop: dict | None = None,
) -> dict:
    stop = dict(park_stop or {})
    if park_stop is not None and stop.get("route") != "park":
        return {
            "ok": False,
            "route": "fail",
            "error": "park_stop_not_admitted",
            "verdict": "park",
        }
    if not live:
        return {"ok": True, "planned": True, "verdict": "park", "route": "park"}
    reason = str(stop.get("reason") or decision.get("reason") or "park")
    summary = str(stop.get("summary") or decision.get("summary") or "").strip()
    note = f"Parked by factory (Lokay): {reason}."
    if summary:
        note = f"{note} {summary}."
    human = str(getattr(cfg, "needs_feedback_label", None) or "ai:needs-feedback")
    labels = [str(x) for x in list(stop.get("labels") or []) if str(x).strip()]
    labels = [x for x in labels if x != human]
    if not labels:
        labels = [MACHINE_PARK_LABEL]
    add_issue_labels(runner, repo, issue, labels, live=True)
    comment_issue(runner, repo, issue, note, live=True)
    return {
        "ok": True,
        "applied": True,
        "verdict": "park",
        "route": "park",
        "labels": labels,
        "reason": reason,
    }
