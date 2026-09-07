"""Admit factory park as a machine stop — never the human needs-feedback mailbox."""

from __future__ import annotations

MACHINE_PARK_LABEL = "ai:frozen"


def select(
    *,
    decision: dict,
    needs_feedback_label: str = "ai:needs-feedback",
) -> dict:
    """Pick park labels. Structured fail stays machine-side (ai:frozen)."""
    payload = dict(decision or {})
    verdict = str(payload.get("verdict") or "").strip().lower()
    if verdict != "park":
        return {"ok": True, "route": "not_applicable", "reason": "not_park"}
    reason = str(payload.get("reason") or "park")
    summary = str(payload.get("summary") or "")
    labels = [MACHINE_PARK_LABEL]
    human = str(needs_feedback_label or "ai:needs-feedback")
    if human in labels:
        return {
            "ok": False,
            "route": "fail",
            "reason": "refusing_human_mailbox_park",
            "labels": [],
        }
    return {
        "ok": True,
        "route": "park",
        "labels": labels,
        "reason": reason,
        "summary": summary,
        "decision": {
            "verdict": "park",
            "reason": reason,
            "summary": summary,
        },
    }
