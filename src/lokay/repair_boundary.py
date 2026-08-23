"""Pure closed contracts for repairing one reviewed PR head."""

from __future__ import annotations
from typing import Any, Mapping
from lokay.pr_review import extract_json_object, PrReviewError

VERDICTS = frozenset({"repaired", "needs_evidence", "needs_human"})
EVIDENCE_KINDS = frozenset(
    {"pr_metadata", "changed_files", "test_contract", "review_findings"}
)
_FIELDS = frozenset(
    {"verdict", "evidence_kind", "summary", "tests_run", "residual_risk"}
)


class RepairResultError(ValueError):
    pass


def parse_output(text: str) -> dict[str, Any]:
    try:
        data = extract_json_object(text)
    except PrReviewError as exc:
        raise RepairResultError(str(exc)) from exc
    unknown = sorted(set(data) - _FIELDS)
    if unknown:
        raise RepairResultError(f"unknown repair fields: {unknown}")
    verdict = str(data.get("verdict") or "").strip().lower()
    if verdict == "implemented":
        verdict = "repaired"
    if verdict not in VERDICTS:
        raise RepairResultError(f"verdict must be one of {sorted(VERDICTS)}")
    kind = str(data.get("evidence_kind") or "").strip() or None
    if kind is not None and kind not in EVIDENCE_KINDS:
        raise RepairResultError(
            f"evidence_kind must be one of {sorted(EVIDENCE_KINDS)} or null"
        )
    if verdict == "needs_evidence" and kind is None:
        raise RepairResultError("needs_evidence requires one evidence_kind")
    if verdict != "needs_evidence" and kind is not None:
        raise RepairResultError("evidence_kind is only valid with needs_evidence")
    tests = data.get("tests_run") or []
    if not isinstance(tests, list) or not all(isinstance(x, str) for x in tests):
        raise RepairResultError("tests_run must be a list of strings")
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
    except RepairResultError as exc:
        return {
            "ok": True,
            "route": "retry",
            "validation_error": str(exc),
            "agent_stdout_tail": str(stdout or "")[-2000:],
        }


def select_initial(
    first: Mapping[str, Any], retry: Mapping[str, Any]
) -> dict[str, Any]:
    candidate = retry if first.get("route") == "retry" else first
    if candidate.get("route") != "valid":
        return {
            "ok": True,
            "route": "human",
            "evidence_kind": "none",
            "decision": {"verdict": "needs_human"},
            "reason": "invalid_repair_json_exhausted",
        }
    decision = dict(candidate.get("decision") or {})
    verdict = decision.get("verdict")
    return {
        "ok": True,
        "route": (
            "evidence"
            if verdict == "needs_evidence"
            else ("repaired" if verdict == "repaired" else "human")
        ),
        "evidence_kind": str(decision.get("evidence_kind") or "none"),
        "decision": decision,
    }


def select_evidence(
    initial: Mapping[str, Any], validation: Mapping[str, Any]
) -> dict[str, Any]:
    if initial.get("route") != "evidence":
        return {"ok": True, "route": "not_applicable"}
    if (
        validation.get("route") != "valid"
        or (validation.get("decision") or {}).get("verdict") != "repaired"
    ):
        return {
            "ok": True,
            "route": "human",
            "decision": {"verdict": "needs_human"},
            "reason": "repair_evidence_exhausted",
        }
    return {
        "ok": True,
        "route": "repaired",
        "decision": dict(validation.get("decision") or {}),
    }


def finalize(initial: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
    return dict(evidence) if initial.get("route") == "evidence" else dict(initial)


def select_test(test: Mapping[str, Any], *, applicable: bool = True) -> dict[str, Any]:
    if not applicable:
        return {"ok": True, "route": "not_applicable"}
    passed = (
        bool(test.get("ok"))
        and not bool(test.get("recorded_red"))
        and (bool(test.get("tested")) or bool(test.get("skipped")))
    )
    return {"ok": True, "route": "pass" if passed else "fail"}


def select_test_repair(
    validation: Mapping[str, Any], *, applicable: bool = True
) -> dict[str, Any]:
    if not applicable:
        return {"ok": True, "route": "not_applicable"}
    if (
        validation.get("route") != "valid"
        or (validation.get("decision") or {}).get("verdict") != "repaired"
    ):
        return {"ok": True, "route": "terminal"}
    return {
        "ok": True,
        "route": "repaired",
        "decision": dict(validation.get("decision") or {}),
    }


def finalize_tests(
    first: Mapping[str, Any], second: Mapping[str, Any], *, applicable: bool = True
) -> dict[str, Any]:
    if not applicable:
        return {"ok": True, "route": "not_applicable"}
    if first.get("route") == "pass" or second.get("route") == "pass":
        return {"ok": True, "route": "publish"}
    return {"ok": True, "route": "terminal"}
