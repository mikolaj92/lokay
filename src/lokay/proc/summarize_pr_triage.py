"""Return the authored PR-triage terminal envelope."""


def summarize(
    *,
    review: dict,
    repair: dict,
    repair_manual: dict,
    manual: dict,
    merge: dict,
    close: dict,
) -> dict:
    decision = dict(review.get("decision") or {})
    verdict = str(decision.get("verdict") or "")
    result = {"review": decision}
    if repair and repair.get("reason") != "condition_not_met":
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
            reason=str(manual.get("reason") or "review_needs_human"),
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
            result.update(
                merged=bool(merge.get("merged") or merge.get("planned")),
                closed_issue=close.get("issue"),
            )
    else:
        return {
            "ok": False,
            "error": f"unrouted PR review verdict: {verdict or 'missing'}",
        }
    return {"ok": True, "result": result}
