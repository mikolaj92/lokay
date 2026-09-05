"""Fala organ bindings for explicit PR-review outcome nodes."""

from __future__ import annotations

from typing import Any


def handle_pr_outcome(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    if atom == "summarize_pr_triage":
        from lokay.proc.summarize_pr_triage import summarize

        return summarize(
            review=up.get("publish_pr_review") or {},
            repair=up.get("pr_repair_verdict") or {},
            repair_manual=up.get("review_repair_manual") or {},
            manual=up.get("review_manual") or {},
            merge=up.get("pr_merge") or {},
            close=up.get("close_issue") or {},
            receipt=up.get("publish_delivery_receipt") or {},
            outcome=up.get("select_pr_triage_outcome") or {},
        )

    if atom == "classify_pr_triage_checks":
        from lokay.proc.classify_pr_triage_checks import classify

        return classify(up.get("pr_checks") or {})

    if atom == "select_pr_triage_outcome":
        from lokay.proc.select_pr_triage_outcome import select

        return select(
            up.get("classify_pr_triage_checks") or {},
            up.get("review_repair_gate") or {},
            up.get("test_local") or {},
        )

    if atom == "pr_repair_verdict":
        selected = up.get("select_pr_triage_outcome") or {}
        review = up.get("publish_pr_review") or {}
        return {
            "ok": True,
            "route": "repair",
            "repairable": True,
            "reason": str(selected.get("reason") or "pr_triage_requested_repair"),
            "review": dict(review.get("decision") or {}),
        }

    if atom == "review_repair_gate":
        from lokay.proc.review_repair_gate import route_review_repair

        if str((up.get("classify_pr_triage_checks") or {}).get("route") or "") in {
            "repair",
            "wait",
        }:
            return {
                "ok": True,
                "route": "not_applicable",
                "reason": "pr_triage_not_review",
            }
        return route_review_repair(up.get("publish_pr_review") or {})

    if atom in {"review_manual", "review_repair_manual"}:
        from lokay.proc.review_terminal import terminal_review

        review = up.get("publish_pr_review") or {}
        decision = review.get("decision") if isinstance(review, dict) else {}
        verdict = str((decision or {}).get("verdict") or "needs_human")
        reason = (
            "review_repair_escalated"
            if atom == "review_repair_manual"
            else "review_needs_human"
        )
        return terminal_review(verdict=verdict, reason=reason)

    return None
