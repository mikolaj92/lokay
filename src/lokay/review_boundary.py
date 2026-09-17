"""Pure contracts for SHA-bound legacy and OpenCodeReview PR review."""

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
    base = {"head_sha": head_sha, "request_changes_count": count_request_changes_reviews(markers)}
    if head_sha and prior is not None:
        return {"ok": True, "route": "cached", **base,
                "decision": {"verdict": str(prior.get("verdict") or "")},
                "merge_ok": bool(prior.get("merge_ok"))}
    return {"ok": True, "route": "agent", **base}


def resolve_structured_sha_review(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Reuse only a digest-verified artifact for the current complete identity."""
    from lokay.config import load_config
    from lokay.pr_review import find_review_for_head
    from lokay.pr_review_io import revalidate_pr_identity
    from lokay.proc._common import runner as make_runner
    from lokay.proc.pr_review_artifacts import load_verified_result

    head = str(evidence.get("head_sha") or "").lower()
    markers = parse_review_markers(list(evidence.get("comments") or []))
    marker = find_review_for_head(markers, head)
    request_changes = count_request_changes_reviews(markers)
    if marker is not None and marker.get("verdict") == "fail_closed":
        return {
            "ok": True, "route": "cached", "head_sha": head,
            "request_changes_count": request_changes,
            "decision": {"verdict": "fail_closed"}, "merge_ok": False,
        }
    if marker is None or not marker.get("artifact_sha256") or not marker.get("result_sha256"):
        return {"ok": True, "route": "agent", "head_sha": head,
                "request_changes_count": request_changes}
    try:
        if not evidence.get("config_path"):
            raise ValueError("review configuration path is required for artifact cache")
        cfg = load_config(str(evidence["config_path"]))
        restored = load_verified_result(
            cfg=cfg, repo=str(evidence.get("repo") or ""), pr=int(evidence.get("pr") or 0),
            head_sha=head, artifact_sha256=str(marker["artifact_sha256"]), evidence=evidence,
        )
        if restored is None or restored.get("review_result_sha256") != marker.get("result_sha256"):
            raise ValueError("artifact identity mismatch")
        fresh = revalidate_pr_identity(
            make_runner(cfg), dict(evidence), live=True, cfg=cfg, branch_prefix=cfg.branch_prefix
        )
        if fresh.get("head_sha") != head or fresh.get("task_identity_sha256") != evidence.get("task_identity_sha256"):
            raise ValueError("live review identity drift")
        if marker.get("verdict") != restored.get("decision", {}).get("verdict"):
            raise ValueError("published verdict conflicts with artifact")
        return {
            "ok": True, "route": "cached", "head_sha": head,
            "request_changes_count": count_request_changes_reviews(parse_review_markers(list(evidence.get("comments") or []))),
            "decision": restored["decision"], "merge_ok": marker.get("merge_ok") is True,
            "artifact_sha256": marker["artifact_sha256"],
        }
    except Exception:
        return {"ok": True, "route": "agent", "head_sha": head,
                "request_changes_count": count_request_changes_reviews(parse_review_markers(list(evidence.get("comments") or [])))}


def validate_review_output(stdout: str) -> dict[str, Any]:
    try:
        decision = coerce_soft_nits(parse_review_output(stdout))
    except PrReviewError as exc:
        return {"ok": True, "route": "retry", "validation_error": str(exc),
                "agent_stdout_tail": str(stdout or "")[-2000:]}
    return {"ok": True, "route": "valid", "decision": decision.to_dict()}


def validation_feedback_prompt(error: str, stdout: str) -> str:
    return (
        "Your previous PR review response was invalid. Return ONLY one JSON object "
        "using the required closed schema. Do not add markdown or prose.\n\n"
        f"Validator feedback: {error}\n\nInvalid response:\n{str(stdout or '')[-2000:]}"
    )


def select_review_decision(
    resolved: Mapping[str, Any], first: Mapping[str, Any], retry: Mapping[str, Any]
) -> dict[str, Any]:
    if resolved.get("route") in {"cached", "policy"}:
        route = str(resolved.get("route"))
        return {"ok": True, "route": route,
                "decision": dict(resolved.get("decision") or {}),
                "merge_ok": bool(resolved.get("merge_ok")),
                "evidence_kind": "none",
                "request_changes_count": int(resolved.get("request_changes_count") or 0)}
    candidate = retry if first.get("route") == "retry" else first
    if candidate.get("route") != "valid":
        return {"ok": True, "route": "fail_closed", "decision": {"verdict": "fail_closed"},
                "evidence_kind": "none", "reason": "invalid_review_json_exhausted",
                "validation_error": str(candidate.get("validation_error") or "invalid review")}
    decision = dict(candidate.get("decision") or {})
    return {"ok": True,
            "route": "evidence" if decision.get("verdict") == "needs_evidence" else "publish",
            "evidence_kind": str(decision.get("evidence_kind") or "none"),
            "decision": decision,
            "request_changes_count": int(resolved.get("request_changes_count") or 0)}


def select_evidence_review(selected: Mapping[str, Any], validation: Mapping[str, Any]) -> dict[str, Any]:
    if selected.get("route") != "evidence":
        return {"ok": True, "route": "not_applicable"}
    if validation.get("route") != "valid":
        return {"ok": True, "route": "fail_closed", "reason": "evidence_review_invalid",
                "decision": {"verdict": "fail_closed"},
                "request_changes_count": int(selected.get("request_changes_count") or 0)}
    decision = dict(validation.get("decision") or {})
    if decision.get("verdict") == "needs_evidence":
        return {"ok": True, "route": "fail_closed", "reason": "evidence_still_insufficient",
                "decision": {"verdict": "fail_closed"}}
    return {"ok": True, "route": "publish", "decision": decision,
            "request_changes_count": int(selected.get("request_changes_count") or 0)}


def finalize_review_selection(selected: Mapping[str, Any], evidence_selected: Mapping[str, Any]) -> dict[str, Any]:
    return dict(evidence_selected) if selected.get("route") == "evidence" else dict(selected)


def select_structured_review(resolved: Mapping[str, Any], validated: Mapping[str, Any]) -> dict[str, Any]:
    """Route only a validated fresh result or fully bound verified cache."""
    if resolved.get("route") == "cached":
        decision = resolved.get("decision")
        head = str(resolved.get("head_sha") or "").lower()
        if isinstance(decision, Mapping) and decision.get("verdict") == "fail_closed":
            return {
                "ok": True, "route": "cached", "decision": {"verdict": "fail_closed"},
                "merge_ok": False,
                "request_changes_count": int(resolved.get("request_changes_count") or 0),
            }
        if (
            not isinstance(decision, Mapping)
            or decision.get("reviewed_head_sha") != head
            or not decision.get("task")
            or not decision.get("task_identity_sha256")
            or not decision.get("review_result_sha256")
            or not resolved.get("artifact_sha256")
            or decision.get("verdict") not in {"approve", "request_changes"}
            or not isinstance(decision.get("findings"), list)
            or bool(decision.get("findings")) != (decision.get("verdict") == "request_changes")
        ):
            return {"ok": True, "route": "fail_closed", "decision": {"verdict": "fail_closed"},
                    "reason": "review_cache_not_verified"}
        return {
            "ok": True, "route": "cached", "decision": dict(decision),
            "merge_ok": resolved.get("merge_ok") is True,
            "request_changes_count": int(resolved.get("request_changes_count") or 0),
            "artifact_sha256": str(resolved.get("artifact_sha256") or ""),
        }
    if resolved.get("route") != "agent":
        return {"ok": True, "route": "fail_closed", "decision": {"verdict": "fail_closed"},
                "reason": "review_cache_not_verified"}
    if validated.get("route") != "valid":
        return {"ok": True, "route": "fail_closed", "decision": {"verdict": "fail_closed"},
                "reason": str(validated.get("error") or validated.get("reason") or "review_result_invalid")}
    decision = dict(validated.get("decision") or {})
    return {"ok": True, "route": "publish", "decision": decision,
            "request_changes_count": 0}
