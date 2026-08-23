"""Pure closed contracts for issue-triage domain outcomes."""

from __future__ import annotations
from typing import Any, Mapping
from lokay.intake import (
    CheckResult,
    check_duplicate_ai_pr,
    check_open,
    check_preflight_incident,
    check_superseded,
)
from lokay.models import Issue
from lokay.pr_review import extract_json_object, PrReviewError
from lokay.triage import is_parked, is_undecided

VERDICTS = frozenset({"ready", "close", "split", "needs_evidence", "needs_human"})
EVIDENCE_KINDS = frozenset({"repo_shape", "named_paths", "linked_prs", "covering_prs"})
_FIELDS = frozenset({"verdict", "reason", "evidence", "evidence_kind", "summary"})


class IssueTriageError(ValueError):
    pass


def resolve_candidate(
    issue: Mapping[str, Any],
    *,
    ready_label: str,
    blocked_label: str,
    needs_feedback_label: str,
) -> dict[str, Any]:
    labels = list(issue.get("labels") or [])
    if is_parked(labels):
        return {"ok": True, "route": "skip", "reason": "parked_frozen"}
    if not is_undecided(
        labels,
        ready_label=ready_label,
        blocked_label=blocked_label,
        needs_feedback_label=needs_feedback_label,
    ):
        return {"ok": True, "route": "skip", "reason": "already_decided"}
    return {"ok": True, "route": "evaluate"}


def resolve_hard_facts(
    issue_data: Mapping[str, Any],
    candidate: Mapping[str, Any],
    linked: Mapping[str, Any],
    covering: Mapping[str, Any],
) -> dict[str, Any]:
    if candidate.get("route") != "evaluate":
        return {
            "ok": True,
            "route": "terminal",
            "decision": {
                "verdict": "skip",
                "reason": str(candidate.get("reason") or "skip"),
            },
        }
    issue = Issue.from_dict(dict(issue_data))
    checks = (
        check_open(state=issue.state),
        check_preflight_incident(issue),
        check_superseded(issue, merged_prs=list(linked.get("merged_prs") or [])),
        check_duplicate_ai_pr(
            issue, covering_prs=list(covering.get("covering_prs") or [])
        ),
    )
    hit = next((c for c in checks if c.verdict in {"close", "blocked"}), None)
    if hit is not None:
        verdict = "close" if hit.verdict == "close" else "blocked"
        return {
            "ok": True,
            "route": "terminal",
            "decision": {"verdict": verdict, "reason": hit.reason},
            "checks": [c.to_dict() for c in checks],
        }
    return {"ok": True, "route": "agent", "checks": [c.to_dict() for c in checks]}


def parse_output(text: str) -> dict[str, Any]:
    try:
        data = extract_json_object(text)
    except PrReviewError as exc:
        raise IssueTriageError(str(exc)) from exc
    unknown = sorted(set(data) - _FIELDS)
    if unknown:
        raise IssueTriageError(f"unknown triage fields: {unknown}")
    verdict = str(data.get("verdict") or "").strip().lower()
    if verdict not in VERDICTS:
        raise IssueTriageError(f"verdict must be one of {sorted(VERDICTS)}")
    evidence = data.get("evidence") or []
    if not isinstance(evidence, list):
        raise IssueTriageError("evidence must be a list")
    kind = str(data.get("evidence_kind") or "").strip() or None
    if kind is not None and kind not in EVIDENCE_KINDS:
        raise IssueTriageError(
            f"evidence_kind must be one of {sorted(EVIDENCE_KINDS)} or null"
        )
    if verdict == "needs_evidence" and kind is None:
        raise IssueTriageError("needs_evidence requires one evidence_kind")
    if verdict != "needs_evidence" and kind is not None:
        raise IssueTriageError("evidence_kind is only valid with needs_evidence")
    return {
        "verdict": verdict,
        "reason": str(data.get("reason") or "agent_triage"),
        "evidence": [str(x) for x in evidence if str(x).strip()][:8],
        "evidence_kind": kind,
        "summary": str(data.get("summary") or ""),
    }


def validate_output(stdout: str) -> dict[str, Any]:
    try:
        return {"ok": True, "route": "valid", "decision": parse_output(stdout)}
    except IssueTriageError as exc:
        return {
            "ok": True,
            "route": "retry",
            "validation_error": str(exc),
            "agent_stdout_tail": str(stdout or "")[-2000:],
        }


def select_initial(
    hard: Mapping[str, Any], first: Mapping[str, Any], retry: Mapping[str, Any]
) -> dict[str, Any]:
    if hard.get("route") == "terminal":
        return {
            "ok": True,
            "route": "publish",
            "evidence_kind": "none",
            "decision": dict(hard.get("decision") or {}),
        }
    candidate = retry if first.get("route") == "retry" else first
    if candidate.get("route") != "valid":
        return {
            "ok": True,
            "route": "publish",
            "evidence_kind": "none",
            "decision": {
                "verdict": "needs_human",
                "reason": "invalid_triage_json_exhausted",
            },
        }
    decision = dict(candidate.get("decision") or {})
    return {
        "ok": True,
        "route": (
            "evidence" if decision.get("verdict") == "needs_evidence" else "publish"
        ),
        "evidence_kind": str(decision.get("evidence_kind") or "none"),
        "decision": decision,
    }


def select_evidence(
    selected: Mapping[str, Any], validation: Mapping[str, Any]
) -> dict[str, Any]:
    if selected.get("route") != "evidence":
        return {"ok": True, "route": "not_applicable"}
    if (
        validation.get("route") != "valid"
        or (validation.get("decision") or {}).get("verdict") == "needs_evidence"
    ):
        return {
            "ok": True,
            "route": "publish",
            "decision": {
                "verdict": "needs_human",
                "reason": "issue_evidence_exhausted",
            },
        }
    return {
        "ok": True,
        "route": "publish",
        "decision": dict(validation.get("decision") or {}),
    }


def finalize(
    selected: Mapping[str, Any], evidence_selected: Mapping[str, Any]
) -> dict[str, Any]:
    return (
        dict(evidence_selected)
        if selected.get("route") == "evidence"
        else dict(selected)
    )
