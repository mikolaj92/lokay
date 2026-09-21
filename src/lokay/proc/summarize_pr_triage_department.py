"""PR sieve receipt. Review + merge. Repair is a verdict, not a child start."""

from lokay.proc.walk_pr_leftover import consumes, leftover_after, skipped_fields


def summarize(
    picked: dict, triage_run: dict, verdict: dict, recovery: dict | None = None,
    *, incomplete_retry_position: str = "head",
) -> dict:
    recovered = dict(recovery or {})
    chosen = dict(verdict or {})
    triage = chosen.get("triage") if isinstance(chosen.get("triage"), dict) else {}
    if not triage:
        blob = triage_run.get("triage") if isinstance(triage_run.get("triage"), dict) else {}
        triage = dict(blob)
    recovery_route = str(recovered.get("route") or "")
    if str(picked.get("route") or "") != "pr" and recovery_route in {"", "no_pr"}:
        chosen.update(
            route=str(picked.get("route") or "skip"), verdict="none", reason=str(picked.get("reason") or "no_open_pr"),
            recovery_route=recovery_route or "no_pr", recovery_reason=str(recovered.get("reason") or ""),
            recovered_pushes=list(recovered.get("recovered") or []),
            repair_push_intent_sha256=str(recovered.get("repair_push_intent_sha256") or ""),
        )
    elif recovery_route in {"fail_closed", "recovered"}:
        chosen.update(
            route="fail_closed" if recovery_route == "fail_closed" else "skip",
            verdict="feedback", repairable=False, merged=False, waiting=True,
            reason=str(
                recovered.get("reason")
                or ("repair_push_recovered" if recovery_route == "recovered" else "repair_push_recovery_failed")
            ),
            recovery_reason=str(
                recovered.get("reason")
                or ("repair_push_recovered" if recovery_route == "recovered" else "repair_push_recovery_failed")
            ),
            recovered_pushes=list(recovered.get("recovered") or []),
            repair_push_intent_sha256=str(
                (recovered.get("recovered") or [{}])[0].get("intent_sha256")
                or recovered.get("repair_push_intent_sha256") or ""
            ),
        )
        triage = {
            "repairable": False,
            "reason": chosen["reason"],
            "merged": False,
            "waiting": True,
        }
    elif recovery_route not in {"review", "no_pr"}:
        chosen.update(
            route="fail_closed", verdict="feedback", repairable=False,
            merged=False, waiting=True, reason="repair_push_recovery_route_invalid",
        )
        triage = {
            "repairable": False, "reason": chosen["reason"],
            "merged": False, "waiting": True,
        }
        chosen["recovery_reason"] = "repair_push_recovery_route_invalid"
        chosen["recovered_pushes"] = []
    recovery_route = str(chosen.get("recovery_route") or recovered.get("route") or "")
    recovery_reason = str(chosen.get("recovery_reason") or recovered.get("reason") or "")
    recovered_pushes = list(chosen.get("recovered_pushes") or recovered.get("recovered") or [])
    repair_push_intent_sha256 = str(
        chosen.get("repair_push_intent_sha256")
        or recovered.get("repair_push_intent_sha256")
        or ((recovered.get("recovered") or [{}])[0].get("intent_sha256") or "")
    )
    if str(picked.get("route") or "") == "pr" and recovery_route == "review":
        if chosen.get("route") in {"skip", "fail_closed"} and not recovered_pushes:
            chosen.update(route="completed", verdict="feedback")
    receipt = {
        "ok": True,
        "department": "pr_triage",
        "route": chosen.get("route") or triage_run.get("route") or picked.get("route") or "none",
        "verdict": chosen.get("verdict") or "none",
        "repo": chosen.get("repo") or picked.get("repo"),
        "pr": chosen.get("pr") or picked.get("pr"),
        "branch": chosen.get("branch") or picked.get("branch"),
        "repair_kind": str(triage.get("repair_kind") or chosen.get("repair_kind") or ""),
        "task": dict(triage.get("task") or chosen.get("task") or {}),
        "findings": list(triage.get("findings") or chosen.get("findings") or []),
        "reviewed_head_sha": str(triage.get("reviewed_head_sha") or chosen.get("reviewed_head_sha") or ""),
        "task_identity_sha256": str(triage.get("task_identity_sha256") or chosen.get("task_identity_sha256") or ""),
        "review_result_sha256": str(triage.get("review_result_sha256") or chosen.get("review_result_sha256") or ""),
        "repair_start_head_sha": str(
            triage.get("repair_start_head_sha") or chosen.get("repair_start_head_sha") or ""
        ),
        "recovery_route": recovery_route,
        "recovery_reason": recovery_reason,
        "recovered_pushes": recovered_pushes,
        "repair_push_intent_sha256": repair_push_intent_sha256,
        "triage": {
            "repairable": bool(triage.get("repairable") or chosen.get("repairable")),
            "reason": triage.get("reason") or chosen.get("reason"),
            "recovery_route": recovery_route,
            "recovery_reason": recovery_reason,
            "recovered_pushes": recovered_pushes,
            "repair_push_intent_sha256": repair_push_intent_sha256,
            "repair_kind": str(triage.get("repair_kind") or chosen.get("repair_kind") or ""),
            "head_sha": str(triage.get("head_sha") or chosen.get("head_sha") or ""),
            "review": dict(triage.get("review") or {}),
            "task": dict(triage.get("task") or chosen.get("task") or {}),
            "findings": list(triage.get("findings") or chosen.get("findings") or []),
            "reviewed_head_sha": str(triage.get("reviewed_head_sha") or chosen.get("reviewed_head_sha") or ""),
            "task_identity_sha256": str(triage.get("task_identity_sha256") or chosen.get("task_identity_sha256") or ""),
            "review_result_sha256": str(triage.get("review_result_sha256") or chosen.get("review_result_sha256") or ""),
            "repair_start_head_sha": str(
                triage.get("repair_start_head_sha") or chosen.get("repair_start_head_sha") or ""
            ),
            "merged": bool(triage.get("merged") or chosen.get("merged")),
            "waiting": bool(triage.get("waiting") or chosen.get("waiting")),
        },
        "repair_started": False,
    }
    # Preserve the structured wait signal in both the public receipt and the
    # queue stamp; reason strings and route=completed cannot encode occupancy.
    receipt["waiting"] = receipt["triage"]["waiting"]
    stamp = {**chosen, **receipt}
    leftover_prs = leftover_after(picked, stamp, incomplete_retry_position=incomplete_retry_position)
    if (incomplete_retry_position == "tail" and recovery_route == "fail_closed"
            and str(picked.get("route") or "") == "pr" and leftover_prs):
        # Uncertainty is KEEP, but it cannot pin the fleet's next selection.
        leftover_prs = [*leftover_prs[1:], leftover_prs[0]]
    if str(picked.get("route") or "") == "pr" or "leftover_prs" in picked:
        receipt["leftover_prs"] = leftover_prs
        receipt["leftover"] = len(leftover_prs)
        if consumes(stamp) and str(picked.get("route") or "") == "pr":
            receipt.update(skipped_fields({
                "skipped_pr": picked.get("pr"),
                "skipped_pr_repo": picked.get("repo"),
                "skipped_head_sha": picked.get("head_sha"),
            }))
        else:
            receipt.update(skipped_fields(picked))
    return {**receipt, "result": dict(receipt)}
