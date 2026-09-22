"""Return the authored PR-triage terminal envelope."""


def summarize(
    *,
    review: dict,
    repair: dict,
    repair_manual: dict,
    manual: dict,
    merge: dict,
    close: dict,
    receipt: dict | None = None,
    outcome: dict | None = None,
) -> dict:
    decision = dict(review.get("decision") or {})
    verdict = str(decision.get("verdict") or "")
    result: dict = {"review": decision}
    selected = dict(outcome or {})
    if selected.get("route") == "wait" or selected.get("waiting"):
        result.update(
            skipped=True,
            reason=str(selected.get("reason") or "checks_pending"),
            waiting=True,
            repairable=False,
        )
        return {"ok": True, "result": result}
    if selected.get("route") == "repair":
        repair_kind = str(selected.get("repair_kind") or "")
        if repair_kind not in {"ci", "review"}:
            return {"ok": False, "error": "repair_kind_missing_or_invalid"}
        result.update(
            skipped=True,
            reason=str(selected.get("reason") or "review_requested_changes"),
            repairable=True,
            repair_kind=repair_kind,
            head_sha=str(selected.get("head_sha") or ""),
            review=decision,
            # Explicit empty CI handoff fields override retained review evidence.
            task=dict(selected.get("task", decision.get("task")) or {}),
            findings=list(selected.get("findings", decision.get("findings")) or []),
            reviewed_head_sha=str(selected.get("reviewed_head_sha", decision.get("reviewed_head_sha")) or ""),
            task_identity_sha256=str(selected.get("task_identity_sha256", decision.get("task_identity_sha256")) or ""),
            review_result_sha256=str(selected.get("review_result_sha256", decision.get("review_result_sha256")) or ""),
            repair_start_head_sha=str(selected.get("repair_start_head_sha") or ""),
        )
    elif repair and repair.get("reason") != "condition_not_met":
        result.update(
            skipped=True,
            reason=str(repair.get("reason") or "review_requested_changes"),
            repairable=False,
            repaired=bool(repair.get("ok")),
        )
    elif repair_manual and repair_manual.get("reason") != "condition_not_met":
        result.update(
            skipped=True,
            reason=str(repair_manual.get("reason") or "review_repair_escalated"),
            repairable=False,
            needs_review=True,
            escalated=bool(review.get("escalated")),
        )
    elif manual and manual.get("reason") != "condition_not_met":
        result.update(
            skipped=True,
            reason=str(
                manual.get("reason")
                or review.get("reason")
                or "review_fail_closed"
            ),
            repairable=False,
            needs_review=True,
        )
    elif verdict == "approve":
        if merge.get("skipped"):
            reason = str(merge.get("reason") or "pr_merge_skipped")
            result.update(
                skipped=True,
                reason=reason,
                repairable=bool(merge.get("repairable")),
                waiting=bool(merge.get("waiting"))
                or reason
                in {"checks_pending", "checks_none_require_checks", "merge_disabled"},
                needs_review=bool(merge.get("needs_review")),
            )
        else:
            confirmed = dict(receipt or {})
            result.update(
                merged=merge.get("merged") is True,
                planned=merge.get("planned") is True,
                issue_closed=confirmed.get("confirmed") is True or confirmed.get("issue_closed") is True or (
                    close.get("ok") is True and close.get("closed") is True
                ),
                closed_issue=close.get("issue") if (
                    confirmed.get("confirmed") is True or confirmed.get("issue_closed") is True or (
                        close.get("ok") is True and close.get("closed") is True
                    )
                ) else 0,
                delivery_confirmed=bool(confirmed.get("confirmed")),
                delivery_receipt=dict(confirmed.get("receipt") or {}),
            )
            if not confirmed.get("confirmed"):
                result["reason"] = str(
                    confirmed.get("reason") or "delivery_receipt_unconfirmed"
                )
    else:
        return {
            "ok": False,
            "error": f"unrouted PR review verdict: {verdict or 'missing'}",
        }
    return {"ok": True, "result": result}
