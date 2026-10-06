import pytest

from lokay.organ.pr_outcome import handle_pr_outcome


@pytest.mark.parametrize("source", ["pr_repair_verdict", "select_pr_triage_outcome"])
def test_failed_ci_repair_handoff_is_never_reported_as_repaired(source):
    result = handle_pr_outcome("summarize_pr_triage", {}, {
        "publish_pr_review": {"decision": {"verdict": "not_applicable"}},
        "select_pr_triage_outcome": {"route": "repair", "repair_kind": "ci"},
        source: {"ok": True, "route": "fail_closed", "reason": "ci_repair_start_head_missing",
                              "repairable": False, "needs_review": True},
    }, {})
    assert result["ok"] is True
    assert result["result"].get("repaired") is not True
    assert result["result"]["waiting"] is True
    assert result["result"]["needs_review"] is True
    assert result["result"]["reason"] == "ci_repair_start_head_missing"


@pytest.mark.parametrize("escalated,secrets", [(True, False), (False, True)])
def test_complete_escalated_review_handoff_does_not_become_pending(escalated, secrets):
    from lokay.proc.walk_pr_leftover import consumes
    from lokay.proc.review_repair_gate import route_review_repair
    from lokay.proc.select_pr_triage_outcome import select
    review = {"escalated": escalated, "decision": {"verdict": "request_changes", "secrets": secrets,
              "task": {"type": "Issue", "state": "OPEN"}, "findings": [{"path": "src/product.py"}],
              "reviewed_head_sha": "b" * 40, "task_identity_sha256": "a" * 64,
              "review_result_sha256": "c" * 64}}
    gate = route_review_repair(review)
    outcome = select({"route": "review"}, gate, {"reason": "condition_not_met"})
    result = handle_pr_outcome("summarize_pr_triage", {}, {
        "publish_pr_review": review,
        "select_pr_triage_outcome": outcome,
        "pr_repair_verdict": {"reason": "condition_not_met"},
        "review_repair_manual": {"ok": True, "needs_review": True, "reason": "review_repair_escalated"},
    }, {})
    assert result["ok"] is True
    assert result["result"].get("repaired") is not True
    assert result["result"].get("waiting") is not True
    assert consumes({"route": "completed", "verdict": "feedback", **result["result"]}) is True


@pytest.mark.parametrize("reason,keep", [
    ("ocr_contract_incomplete: finding anchor is not within changed lines", True),
    ("ocr_contract_rejected: review has warnings", False),
])
def test_published_semantic_rejection_preserves_existing_consumption_policy(reason, keep):
    from lokay.proc.walk_pr_leftover import consumes
    result = handle_pr_outcome("summarize_pr_triage", {}, {
        "publish_pr_review": {"decision": {"verdict": "fail_closed"}, "reason": reason},
        "select_pr_triage_outcome": {"route": "none", "reason": "no_merge_path"},
        "review_manual": {"ok": True, "needs_review": True, "reason": reason},
        "pr_repair_verdict": {"reason": "condition_not_met"},
    }, {})
    assert result["ok"] is True
    assert consumes({"route": "completed", "verdict": "feedback", **result["result"]}) is not keep
