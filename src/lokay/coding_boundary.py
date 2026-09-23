"""Pure closed contracts for the issue implementation boundary."""

from __future__ import annotations
import json
from typing import Any, Mapping

VERDICTS = frozenset({"implemented", "needs_evidence"})
EVIDENCE_KINDS = frozenset(
    {"issue_snapshot", "repo_structure", "test_contract", "localized_diff"}
)
_FIELDS = frozenset(
    {"verdict", "evidence_kind", "summary", "tests_run", "residual_risk"}
)


class CodingResultError(ValueError):
    pass


def parse_output(text: str) -> dict[str, Any]:
    # The whole stdout is the result: one object, no prose, no fences, no second value.
    raw = (text or "").strip()
    try:
        data = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, CodingResultError) as exc:
        raise CodingResultError(f"coding result must be exactly one JSON object: {exc}") from exc
    if not isinstance(data, dict):
        raise CodingResultError("coding result must be a JSON object")
    unknown = sorted(set(data) - _FIELDS)
    if unknown:
        raise CodingResultError(f"unknown coding fields: {unknown}")
    missing = sorted(_FIELDS - set(data))
    if missing:
        raise CodingResultError(f"missing coding fields: {missing}")
    if not isinstance(data.get("verdict"), str):
        raise CodingResultError("verdict must be a string")
    verdict = data["verdict"].strip().lower()
    if verdict not in VERDICTS:
        raise CodingResultError(f"verdict must be one of {sorted(VERDICTS)}")
    raw_kind = data.get("evidence_kind")
    if raw_kind is not None and not isinstance(raw_kind, str):
        raise CodingResultError("evidence_kind must be a string or null")
    kind = str(raw_kind or "").strip() or None
    if kind is not None and kind not in EVIDENCE_KINDS:
        raise CodingResultError(
            f"evidence_kind must be one of {sorted(EVIDENCE_KINDS)} or null"
        )
    if verdict == "needs_evidence" and kind is None:
        raise CodingResultError("needs_evidence requires one evidence_kind")
    if verdict != "needs_evidence" and kind is not None:
        raise CodingResultError("evidence_kind is only valid with needs_evidence")
    tests = data.get("tests_run")
    if not isinstance(tests, list) or not all(isinstance(x, str) for x in tests):
        raise CodingResultError("tests_run must be a list of strings")
    for field in ("summary", "residual_risk"):
        if not isinstance(data.get(field), str):
            raise CodingResultError(f"{field} must be a string")
    return {
        "verdict": verdict,
        "evidence_kind": kind,
        "summary": data["summary"],
        "tests_run": [x for x in tests if x.strip()][:12],
        "residual_risk": data["residual_risk"],
    }


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise CodingResultError(f"duplicate key: {key}")
        seen[key] = value
    return seen


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
            "decision": {"verdict": "fail_closed"},
            "reason": str(first.get("reason") or "localize_empty"),
        }
    candidate = retry if first.get("route") == "retry" else first
    if candidate.get("route") != "valid":
        return {
            "ok": True,
            "route": "fail_closed",
            "evidence_kind": "none",
            "decision": {"verdict": "fail_closed"},
            "reason": "invalid_coding_json_exhausted",
        }
    decision = dict(candidate.get("decision") or {})
    return {
        "ok": True,
        "route": (
            "evidence"
            if decision.get("verdict") == "needs_evidence"
            else (
                "implemented"
                if decision.get("verdict") == "implemented"
                else "fail_closed"
            )
        ),
        "evidence_kind": str(decision.get("evidence_kind") or "none"),
        "decision": decision,
        "session": candidate.get("session"),
    }


def select_evidence(
    selected: Mapping[str, Any], validation: Mapping[str, Any]
) -> dict[str, Any]:
    if selected.get("route") != "evidence":
        return {"ok": True, "route": "not_applicable"}
    if validation.get("route") != "valid":
        return {
            "ok": True,
            "route": "fail_closed",
            "decision": {"verdict": "fail_closed"},
            "reason": "evidence_coding_invalid",
        }
    decision = dict(validation.get("decision") or {})
    if decision.get("verdict") != "implemented":
        return {
            "ok": True,
            "route": "fail_closed",
            "decision": {"verdict": "fail_closed"},
            "reason": "coding_evidence_exhausted",
        }
    return {"ok": True, "route": "implemented", "decision": decision,
            "session": validation.get("session")}


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
    first: Mapping[str, Any],
    applicable: bool = True,
    retry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Map coding select_initial onto local_repair routes (no human / evidence).

    One invalid-JSON retry budget (like coding). Implemented → repaired;
    fail_closed / failed / evidence → terminal. needs_human is not a verdict.
    """
    if not applicable:
        return {"ok": True, "route": "not_applicable"}
    selected = select_initial(first, retry or {})
    route = str(selected.get("route") or "")
    decision = dict(selected.get("decision") or {})
    if route == "implemented" and decision.get("verdict") == "implemented":
        return {"ok": True, "route": "repaired", "decision": decision}
    reason = str(selected.get("reason") or "")
    if not reason:
        if route == "evidence":
            reason = "repair_fail_closed"
        elif route == "fail_closed":
            reason = "invalid_repair_json"
        else:
            reason = "repair_fail_closed"
    out: dict[str, Any] = {
        "ok": True,
        "route": "terminal",
        "reason": reason,
        "decision": decision or {"verdict": "fail_closed"},
    }
    return out
