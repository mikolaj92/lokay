"""Map a PR sieve result to merge / feedback / repair. Does not start repair."""

from __future__ import annotations

from typing import Any, Mapping

from lokay.envelope import ok


def classify(triage_run: Mapping[str, Any]) -> dict:
    """First block: read the child pr_triage envelope."""
    triage = triage_run.get("triage")
    blob = triage if isinstance(triage, Mapping) else triage_run
    return {
        "repairable": bool(blob.get("repairable")),
        "merged": bool(blob.get("merged")),
        "waiting": bool(blob.get("waiting")),
        "reason": str(blob.get("reason") or triage_run.get("reason") or ""),
        "repair_kind": str(blob.get("repair_kind") or triage_run.get("repair_kind") or ""),
        "head_sha": str(blob.get("head_sha") or triage_run.get("head_sha") or ""),
        "review": dict(blob.get("review") or {}),
        "task": dict(blob.get("task") or {}),
        "findings": list(blob.get("findings") or []),
        "reviewed_head_sha": str(blob.get("reviewed_head_sha") or ""),
        "task_identity_sha256": str(blob.get("task_identity_sha256") or ""),
        "review_result_sha256": str(blob.get("review_result_sha256") or ""),
        "repair_start_head_sha": str(blob.get("repair_start_head_sha") or ""),
    }


def select(
    picked: Mapping[str, Any], triage_run: Mapping[str, Any],
    recovery: Mapping[str, Any] | None = None,
) -> dict:
    """Second block: verdict only. repair does not invoke pr_repair."""
    recovered = dict(recovery or {})
    recovery_route = str(recovered.get("route") or "")
    if str(picked.get("route") or "") != "pr":
        return ok(
            route="skip", verdict="none",
            reason=str(picked.get("reason") or "no_open_pr"),
            recovery_route=recovery_route,
            recovery_reason=str(recovered.get("reason") or ""),
            recovered_pushes=list(recovered.get("recovered") or []),
            repair_push_intent_sha256=str(recovered.get("repair_push_intent_sha256") or ""),
        )
    if recovery_route in {"fail_closed", "recovered"}:
        reason = str(
            recovered.get("reason")
            or ("repair_push_recovered" if recovery_route == "recovered" else "repair_push_recovery_failed")
        )
        picked_facts = dict(picked or {})
        picked_facts.pop("route", None)
        return ok(
            route="fail_closed" if recovery_route == "fail_closed" else "skip",
            verdict="feedback", repairable=False, merged=False, waiting=True,
            reason=reason, recovery_route=recovery_route,
            recovered=list(recovered.get("recovered") or []),
            repair_push_intent_sha256=(
                str((recovered.get("recovered") or [{}])[0].get("intent_sha256") or "")
                if recovered.get("recovered") else str(recovered.get("repair_push_intent_sha256") or "")
            ),
            triage={
                "repairable": False,
                "reason": reason,
                "merged": False,
                "waiting": True,
                "recovery_route": recovery_route,
                "recovery_reason": str(recovered.get("reason") or reason),
                "recovered_pushes": list(recovered.get("recovered") or []),
                "repair_push_intent_sha256": (
                    str((recovered.get("recovered") or [{}])[0].get("intent_sha256") or "")
                    if recovered.get("recovered") else str(recovered.get("repair_push_intent_sha256") or "")
                ),
            },
            recovery_reason=str(recovered.get("reason") or reason),
            recovered_pushes=list(recovered.get("recovered") or []),
            **picked_facts,
        )
    if recovery_route != "review":
        picked_facts = dict(picked or {})
        picked_facts.pop("route", None)
        return ok(
            route="fail_closed", verdict="feedback", repairable=False,
            merged=False, waiting=True, reason="repair_push_recovery_route_invalid",
            recovery_route=recovery_route,
            triage={
                "repairable": False, "reason": "repair_push_recovery_route_invalid",
                "merged": False, "waiting": True,
                "recovery_route": recovery_route,
                "recovery_reason": "repair_push_recovery_route_invalid",
            },
            recovery_reason="repair_push_recovery_route_invalid",
            recovered_pushes=[],
            **picked_facts,
        )
    facts = classify(triage_run)
    if facts["merged"]:
        verdict = "merge"
    elif facts["repairable"]:
        verdict = "repair"
    elif facts["waiting"]:
        verdict = "feedback"
    else:
        verdict = "feedback"
    return ok(
        route="completed",
        verdict=verdict,
        repairable=facts["repairable"],
        merged=facts["merged"],
        waiting=facts["waiting"],
        reason=facts["reason"] or verdict,
        repair_kind=facts["repair_kind"],
        head_sha=facts["head_sha"],
        review=facts["review"],
        task=facts["task"],
        findings=facts["findings"],
        reviewed_head_sha=facts["reviewed_head_sha"],
        task_identity_sha256=facts["task_identity_sha256"],
        review_result_sha256=facts["review_result_sha256"],
        repair_start_head_sha=facts["repair_start_head_sha"],
        repo=picked.get("repo"),
        pr=picked.get("pr"),
        branch=picked.get("branch"),
        triage={
            "repairable": facts["repairable"],
            "reason": facts["reason"] or verdict,
            "repair_kind": facts["repair_kind"],
            "head_sha": facts["head_sha"],
            "review": facts["review"],
            "task": facts["task"],
            "findings": facts["findings"],
            "reviewed_head_sha": facts["reviewed_head_sha"],
            "task_identity_sha256": facts["task_identity_sha256"],
            "review_result_sha256": facts["review_result_sha256"],
            "repair_start_head_sha": facts["repair_start_head_sha"],
            "merged": facts["merged"],
            "waiting": facts["waiting"],
        },
    )
