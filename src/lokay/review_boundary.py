"""Pure contracts for the SHA-bound PR review boundary."""

from __future__ import annotations

from typing import Any, Mapping

from lokay.pr_review import (
    PrReviewError, coerce_soft_nits, count_request_changes_reviews,
    find_review_for_head, parse_review_markers, parse_review_output,
)


def resolve_sha_review(evidence: Mapping[str, Any]) -> dict[str, Any]:
    head_sha = str(evidence.get("head_sha") or "").strip().lower()
    markers = parse_review_markers(list(evidence.get("comments") or []))
    prior = find_review_for_head(markers, head_sha)
    base = {
        "head_sha": head_sha,
        "request_changes_count": count_request_changes_reviews(markers),
    }
    if head_sha and prior is not None:
        return {
            "ok": True, "route": "cached", **base,
            "decision": {"verdict": str(prior.get("verdict") or "")},
            "merge_ok": bool(prior.get("merge_ok")),
        }
    return {"ok": True, "route": "agent", **base}


def validate_review_output(stdout: str) -> dict[str, Any]:
    try:
        decision = coerce_soft_nits(parse_review_output(stdout))
    except PrReviewError as exc:
        return {
            "ok": True, "route": "retry", "validation_error": str(exc),
            "agent_stdout_tail": str(stdout or "")[-2000:],
        }
    return {"ok": True, "route": "valid", "decision": decision.to_dict()}


def validation_feedback_prompt(error: str, stdout: str) -> str:
    return (
        "Your previous PR review response was invalid. Return ONLY one JSON object "
        "using the required closed schema. Do not add markdown or prose.\n\n"
        f"Validator feedback: {error}\n\n"
        f"Invalid response:\n{str(stdout or '')[-2000:]}"
    )


def select_review_decision(
    resolved: Mapping[str, Any], first: Mapping[str, Any], retry: Mapping[str, Any]
) -> dict[str, Any]:
    if resolved.get("route") in {"cached", "policy"}:
        route = str(resolved.get("route"))
        return {
            "ok": True, "route": route,
            "decision": dict(resolved.get("decision") or {}),
            "merge_ok": bool(resolved.get("merge_ok")),
            "evidence_kind": "none",
            "request_changes_count": int(resolved.get("request_changes_count") or 0),
        }
    candidate = retry if first.get("route") == "retry" else first
    if candidate.get("route") != "valid":
        return {
            "ok": True, "route": "needs_human",
            "decision": {"verdict": "needs_human"},
            "evidence_kind": "none",
            "reason": "invalid_review_json_exhausted",
            "validation_error": str(candidate.get("validation_error") or "invalid review"),
        }
    decision = dict(candidate.get("decision") or {})
    return {
        "ok": True,
        "route": "evidence" if decision.get("verdict") == "needs_evidence" else "publish",
        "evidence_kind": str(decision.get("evidence_kind") or "none"),
        "decision": decision,
        "request_changes_count": int(resolved.get("request_changes_count") or 0),
    }


def select_evidence_review(
    selected: Mapping[str, Any], validation: Mapping[str, Any]
) -> dict[str, Any]:
    if selected.get("route") != "evidence":
        return {"ok": True, "route": "not_applicable"}
    if validation.get("route") != "valid":
        return {
            "ok": True, "route": "needs_human",
            "reason": "evidence_review_invalid",
            "decision": {"verdict": "needs_human"},
            "request_changes_count": int(selected.get("request_changes_count") or 0),
        }
    decision = dict(validation.get("decision") or {})
    if decision.get("verdict") == "needs_evidence":
        return {
            "ok": True, "route": "needs_human",
            "reason": "evidence_still_insufficient",
            "decision": {"verdict": "needs_human"},
        }
    return {
        "ok": True, "route": "publish", "decision": decision,
        "request_changes_count": int(selected.get("request_changes_count") or 0),
    }


def finalize_review_selection(
    selected: Mapping[str, Any], evidence_selected: Mapping[str, Any]
) -> dict[str, Any]:
    if selected.get("route") == "evidence":
        return dict(evidence_selected)
    return dict(selected)
