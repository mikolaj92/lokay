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
            outcome=up.get("pr_repair_verdict") or up.get("select_pr_triage_outcome") or {},
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
        repair_kind = str(selected.get("repair_kind") or "")
        decision = dict(review.get("decision") or {})
        task = dict(decision.get("task") or {})
        findings = decision.get("findings") if isinstance(decision.get("findings"), list) else []
        reviewed_sha = str(decision.get("reviewed_head_sha") or "")
        task_digest = str(decision.get("task_identity_sha256") or "")
        review_digest = str(decision.get("review_result_sha256") or "")
        if not repair_kind:
            return {
                "ok": True, "route": "fail_closed", "repairable": False,
                "reason": "repair_kind_invalid", "needs_review": True,
            }
        if repair_kind == "ci":
            start_head_sha = str(selected.get("head_sha") or "").lower()
            import re
            if not re.fullmatch(r"[a-f0-9]{40}", start_head_sha):
                return {
                    "ok": True, "route": "fail_closed", "repairable": False,
                    "reason": "ci_repair_start_head_missing", "needs_review": True,
                }
            return {
                "ok": True, "route": "repair", "repairable": True,
                "reason": str(selected.get("reason") or "checks_failed"),
                "repair_kind": "ci", "head_sha": start_head_sha, "review": decision,
                "task": {}, "findings": [], "reviewed_head_sha": "",
                "task_identity_sha256": "", "review_result_sha256": "",
            }
        if repair_kind != "review" or (
            decision.get("verdict") != "request_changes" or not task or not findings
            or not reviewed_sha or not task_digest or not review_digest
            or str(selected.get("repair_start_head_sha") or "").lower() != reviewed_sha.lower()
        ):
            return {
                "ok": True, "route": "fail_closed", "repairable": False,
                "reason": "review_repair_handoff_incomplete", "needs_review": True,
            }
        return {
            "ok": True,
            "route": "repair",
            "repairable": True,
            "reason": str(selected.get("reason") or "pr_triage_requested_repair"),
            "review": decision,
            "task": task,
            "findings": findings,
            "reviewed_head_sha": reviewed_sha,
            "task_identity_sha256": task_digest,
            "review_result_sha256": review_digest,
            "repair_kind": "review",
            "repair_start_head_sha": reviewed_sha,
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
        verdict = str((decision or {}).get("verdict") or "fail_closed")
        reason = (
            "review_repair_escalated"
            if atom == "review_repair_manual"
            else "review_fail_closed"
        )
        return terminal_review(verdict=verdict, reason=reason)

    return None
