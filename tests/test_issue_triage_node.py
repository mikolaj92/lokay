"""Authored issue_triage NODE: leaves + issue_split child; receipt always."""

import tomllib

from lokay.graph_run import find_default_package


def _raw() -> dict:
    pkg = tomllib.loads(find_default_package().read_text(encoding="utf-8"))
    return next(p for p in pkg["correlation_paths"] if p["id"] == "issue_triage")


def _lookup(envelope: dict, path: str) -> str:
    cur: object = envelope
    for part in path.split("."):
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(part)
    return str(cur or "")


def simulate_issue_triage(facts: dict[str, dict]) -> dict[str, str]:
    """Apply authored conduction + when. Skipped upstream satisfies conduction."""
    status: dict[str, str] = {}

    def matches(when: dict) -> bool:
        if not when:
            return True
        upstream = str(when.get("upstream") or "")
        if status.get(upstream) != "succeeded":
            return False
        return _lookup(facts.get(upstream) or {}, str(when.get("path") or "")) == str(
            when.get("equals") or ""
        )

    pending = list(_raw()["effectors"])
    progressed = True
    while pending and progressed:
        progressed = False
        leftover = []
        for node in pending:
            deps = list(node.get("conduction") or [])
            if any(status.get(dep) not in {"succeeded", "skipped"} for dep in deps):
                leftover.append(node)
                continue
            name = str(node["id"])
            status[name] = "succeeded" if matches(dict(node.get("when") or {})) else "skipped"
            progressed = True
        pending = leftover
    assert not pending, [node["id"] for node in pending]
    return status


def test_already_decided_skips_agent_and_still_receipts():
    status = simulate_issue_triage(
        {
            "resolve_issue_candidate": {"route": "skip"},
            "resolve_issue_hard_facts": {"route": "terminal"},
            "validate_issue_triage": {"route": "not_applicable"},
            "select_issue_triage": {"evidence_kind": "none"},
            "verify_issue_evidence": {"route": "not_applicable"},
            "finalize_issue_triage": {"decision": {"verdict": "skip"}},
        }
    )
    assert status["collect_issue_linked_prs"] == "skipped"
    assert status["issue_triage_agent"] == "skipped"
    assert status["issue_split_subflow"] == "skipped"
    assert status["apply_issue_ready"] == "skipped"
    assert status["summarize_issue_triage"] == "succeeded"


def test_ready_applies_only_ready_then_receipt():
    status = simulate_issue_triage(
        {
            "resolve_issue_candidate": {"route": "evaluate"},
            "resolve_issue_hard_facts": {"route": "agent"},
            "validate_issue_triage": {"route": "valid"},
            "select_issue_triage": {"evidence_kind": "none"},
            "verify_issue_evidence": {"route": "not_applicable"},
            "finalize_issue_triage": {"decision": {"verdict": "ready"}},
        }
    )
    assert status["issue_triage_agent"] == "succeeded"
    assert status["issue_triage_retry_agent"] == "skipped"
    assert status["apply_issue_ready"] == "succeeded"
    assert status["apply_issue_close"] == "skipped"
    assert status["issue_split_subflow"] == "skipped"
    assert status["summarize_issue_triage"] == "succeeded"


def test_split_invokes_child_fala_then_receipt():
    status = simulate_issue_triage(
        {
            "resolve_issue_candidate": {"route": "evaluate"},
            "resolve_issue_hard_facts": {"route": "agent"},
            "validate_issue_triage": {"route": "valid"},
            "select_issue_triage": {"evidence_kind": "none"},
            "verify_issue_evidence": {"route": "not_applicable"},
            "finalize_issue_triage": {"decision": {"verdict": "split"}},
        }
    )
    assert status["issue_split_subflow"] == "succeeded"
    assert status["apply_issue_ready"] == "skipped"
    assert status["apply_issue_manual"] == "skipped"
    assert status["summarize_issue_triage"] == "succeeded"
