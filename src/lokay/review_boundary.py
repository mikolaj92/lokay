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
            "request_changes_count": int(resolved.get("request_changes_count") or 0),
        }
    candidate = retry if first.get("route") == "retry" else first
    if candidate.get("route") != "valid":
        return {
            "ok": True, "route": "needs_human",
            "reason": "invalid_review_json_exhausted",
            "validation_error": str(candidate.get("validation_error") or "invalid review"),
        }
    return {
        "ok": True, "route": "publish",
        "decision": dict(candidate.get("decision") or {}),
        "request_changes_count": int(resolved.get("request_changes_count") or 0),
    }
