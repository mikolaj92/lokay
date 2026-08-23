"""Closed PR-review boundary contracts."""

from lokay.review_boundary import (
    resolve_sha_review, select_review_decision, validate_review_output,
    validation_feedback_prompt,
)


def test_resolve_same_sha_preserves_domain_verdict_not_cache_status():
    evidence={"head_sha":"abc123","comments":["<!-- lokay-review head=abc123 verdict=request_changes merge_ok=0 -->"]}
    out=resolve_sha_review(evidence)
    assert out["route"] == "cached"
    assert out["decision"] == {"verdict":"request_changes"}


def test_resolve_new_sha_requests_agent():
    evidence={"head_sha":"new123","comments":["<!-- lokay-review head=old123 verdict=approve merge_ok=1 -->"]}
    assert resolve_sha_review(evidence)["route"] == "agent"


def test_invalid_output_routes_retry_with_feedback():
    out=validate_review_output("not json")
    assert out["ok"] is True and out["route"] == "retry"
    prompt=validation_feedback_prompt(out["validation_error"],out["agent_stdout_tail"])
    assert "Validator feedback" in prompt and "not json" in prompt


def test_valid_retry_becomes_authoritative_domain_result():
    first=validate_review_output("bad")
    retry=validate_review_output('{"verdict":"approve","secrets":false,"blocking":[]}')
    out=select_review_decision({"route":"agent","request_changes_count":0},first,retry)
    assert out["route"] == "publish"
    assert out["decision"]["verdict"] == "approve"


def test_second_invalid_result_is_terminal_needs_human():
    first=validate_review_output("bad one")
    retry=validate_review_output("bad two")
    out=select_review_decision({"route":"agent"},first,retry)
    assert out["route"] == "needs_human"
    assert out["reason"] == "invalid_review_json_exhausted"


def test_cached_verdict_ignores_skipped_validation_nodes():
    out=select_review_decision(
        {"route":"cached","decision":{"verdict":"request_changes"},"merge_ok":False},
        {"reason":"condition_not_met"},{"reason":"condition_not_met"},
    )
    assert out["route"] == "cached"
    assert out["decision"]["verdict"] == "request_changes"


def test_cached_first_validation_is_not_applicable_at_organ_boundary():
    from lokay.organ.review_boundary import handle_review_boundary
    out=handle_review_boundary("validate_pr_review",{}, {"resolve_sha_review":{"route":"cached"}}, {"repo":"a/b","pr_number":7,"branch":"b","live":[]})
    assert out == {"ok":True,"route":"not_applicable"}


def test_policy_approval_skips_agent_results():
    out=select_review_decision({"route":"policy","decision":{"verdict":"approve"},"merge_ok":True},{"reason":"condition_not_met"},{"reason":"condition_not_met"})
    assert out["route"] == "policy" and out["decision"]["verdict"] == "approve"
