"""Admit former park as skip — never stamp a limbo label on the issue."""

from __future__ import annotations

from lokay.triage import MACHINE_PARK_LABEL

__all__ = ["MACHINE_PARK_LABEL", "select"]


def select(
    *,
    decision: dict,
    needs_feedback_label: str = "ai:needs-feedback",
) -> dict:
    """Map park verdict to skip with zero labels (no ai:frozen limbo).

    Dark factory legal exits: ready | split | skip | close. Local retry/cooldown
    lives in factory state — never a durable GitHub process label.
    """
    payload = dict(decision or {})
    verdict = str(payload.get("verdict") or "").strip().lower()
    if verdict != "park":
        return {"ok": True, "route": "not_applicable", "reason": "not_park"}
    reason = str(payload.get("reason") or "park")
    summary = str(payload.get("summary") or "")
    human = str(needs_feedback_label or "ai:needs-feedback")
    # Refuse any path that would stamp limbo (frozen / human mailbox).
    if human == MACHINE_PARK_LABEL:
        return {
            "ok": False,
            "route": "fail",
            "reason": "refusing_limbo_park",
            "labels": [],
        }
    return {
        "ok": True,
        "route": "skip",
        "labels": [],
        "reason": reason,
        "summary": summary,
        "decision": {
            "verdict": "skip",
            "reason": reason,
            "summary": summary,
        },
    }
