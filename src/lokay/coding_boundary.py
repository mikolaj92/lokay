"""Pure closed contracts for the issue implementation boundary."""

from __future__ import annotations
from typing import Any, Mapping
from lokay.pr_review import extract_json_object, PrReviewError

VERDICTS = frozenset({"implemented", "needs_evidence", "needs_human"})
EVIDENCE_KINDS = frozenset(
    {"issue_snapshot", "repo_structure", "test_contract", "localized_diff"}
)
_FIELDS = frozenset(
    {"verdict", "evidence_kind", "summary", "tests_run", "residual_risk"}
)


class CodingResultError(ValueError):
    pass


def parse_output(text: str) -> dict[str, Any]:
    try:
        data = extract_json_object(text)
    except PrReviewError as exc:
        raise CodingResultError(str(exc)) from exc
    unknown = sorted(set(data) - _FIELDS)
    if unknown:
        raise CodingResultError(f"unknown coding fields: {unknown}")
    verdict = str(data.get("verdict") or "").strip().lower()
    if verdict not in VERDICTS:
        raise CodingResultError(f"verdict must be one of {sorted(VERDICTS)}")
    kind = str(data.get("evidence_kind") or "").strip() or None
    if kind is not None and kind not in EVIDENCE_KINDS:
        raise CodingResultError(
            f"evidence_kind must be one of {sorted(EVIDENCE_KINDS)} or null"
        )
    if verdict == "needs_evidence" and kind is None:
        raise CodingResultError("needs_evidence requires one evidence_kind")
    if verdict != "needs_evidence" and kind is not None:
        raise CodingResultError("evidence_kind is only valid with needs_evidence")
    tests = data.get("tests_run") or []
    if not isinstance(tests, list) or not all(isinstance(x, str) for x in tests):
        raise CodingResultError("tests_run must be a list of strings")
    return {
        "verdict": verdict,
        "evidence_kind": kind,
        "summary": str(data.get("summary") or ""),
        "tests_run": [x for x in tests if x.strip()][:12],
        "residual_risk": str(data.get("residual_risk") or ""),
    }


def validate_output(stdout: str) -> dict[str, Any]:
    try:
        return {"ok": True, "route": "valid", "decision": parse_output(stdout)}
    except CodingResultError as exc:
        return {
            "ok": True,
            "route": "retry",
            "validation_error": str(exc),
            "agent_stdout_tail": str(stdout or "")[-2000:],
        }


def select_initial(
    first: Mapping[str, Any], retry: Mapping[str, Any]
) -> dict[str, Any]:
    if first.get("route") == "empty":
        return {
            "ok": True,
            "route": "failed",
            "evidence_kind": "none",
            "decision": {"verdict": "needs_human"},
            "reason": str(first.get("reason") or "localize_empty"),
        }
    candidate = retry if first.get("route") == "retry" else first
    if candidate.get("route") != "valid":
        return {
            "ok": True,
            "route": "human",
            "evidence_kind": "none",
            "decision": {"verdict": "needs_human"},
            "reason": "invalid_coding_json_exhausted",
        }
    decision = dict(candidate.get("decision") or {})
    return {
        "ok": True,
        "route": (
            "evidence"
            if decision.get("verdict") == "needs_evidence"
            else (
                "implemented" if decision.get("verdict") == "implemented" else "human"
            )
        ),
        "evidence_kind": str(decision.get("evidence_kind") or "none"),
        "decision": decision,
    }


def select_evidence(
    selected: Mapping[str, Any], validation: Mapping[str, Any]
) -> dict[str, Any]:
    if selected.get("route") != "evidence":
        return {"ok": True, "route": "not_applicable"}
    if validation.get("route") != "valid":
        return {
            "ok": True,
            "route": "human",
            "decision": {"verdict": "needs_human"},
            "reason": "evidence_coding_invalid",
        }
    decision = dict(validation.get("decision") or {})
    if decision.get("verdict") != "implemented":
        return {
            "ok": True,
            "route": "human",
            "decision": {"verdict": "needs_human"},
            "reason": "coding_evidence_exhausted",
        }
    return {"ok": True, "route": "implemented", "decision": decision}


def finalize(
    selected: Mapping[str, Any], evidence: Mapping[str, Any]
) -> dict[str, Any]:
    return dict(evidence) if selected.get("route") == "evidence" else dict(selected)


def select_test(result: Mapping[str, Any], applicable: bool = True) -> dict[str, Any]:
    if not applicable:
        return {"ok": True, "route": "not_applicable"}
    passed = (
        bool(result.get("ok"))
        and not bool(result.get("recorded_red"))
        and (bool(result.get("tested")) or bool(result.get("skipped")))
    )
    return {"ok": True, "route": "pass" if passed else "fail", "passed": passed}


def finalize_tests(
    first: Mapping[str, Any], repaired: Mapping[str, Any], applicable: bool = True
) -> dict[str, Any]:
    if not applicable:
        return {"ok": True, "route": "not_applicable"}
    if first.get("route") == "pass":
        return {"ok": True, "route": "publish"}
    if repaired.get("route") == "pass":
        return {"ok": True, "route": "publish"}
    return {"ok": True, "route": "repair_terminal"}


def select_repair(
    validation: Mapping[str, Any], applicable: bool = True
) -> dict[str, Any]:
    if not applicable:
        return {"ok": True, "route": "not_applicable"}
    if validation.get("route") != "valid":
        return {"ok": True, "route": "terminal", "reason": "invalid_repair_json"}
    decision = dict(validation.get("decision") or {})
    if decision.get("verdict") != "implemented":
        return {
            "ok": True,
            "route": "terminal",
            "reason": "repair_needs_human",
            "decision": decision,
        }
    return {"ok": True, "route": "repaired", "decision": decision}
