"""Closed PR-review boundary contracts."""

from lokay.review_boundary import (
    finalize_review_selection, resolve_sha_review, select_evidence_review,
    select_review_decision, validate_review_output, validation_feedback_prompt,
)


def test_resolve_same_sha_preserves_domain_verdict_not_cache_status():
    head = "a" * 40
    evidence={"head_sha":head,"comments":[f"<!-- lokay-review head={head} verdict=request_changes merge_ok=0 -->"]}
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


def test_verified_structured_cache_preserves_complete_decision_and_merge_policy():
    from lokay.review_boundary import select_structured_review

    head = "a" * 40
    decision = {
        "verdict": "approve",
        "findings": [],
        "reviewed_head_sha": head,
        "task_identity_sha256": "b" * 64,
        "review_result_sha256": "c" * 64,
        "task": {"repo": "o/r", "type": "Issue", "state": "OPEN"},
    }
    resolved = {
        "route": "cached", "head_sha": head, "artifact_sha256": "d" * 64,
        "decision": decision, "merge_ok": True, "request_changes_count": 1,
    }

    selected = select_structured_review(resolved, {})

    assert selected["route"] == "cached"
    assert selected["decision"] == decision
    assert selected["merge_ok"] is True
    assert selected["request_changes_count"] == 1


def test_structured_cache_without_artifact_or_bound_decision_fails_closed():
    from lokay.review_boundary import select_structured_review

    resolved = {
        "route": "cached", "head_sha": "a" * 40,
        "decision": {"verdict": "approve", "findings": []}, "merge_ok": True,
    }

    selected = select_structured_review(resolved, {})

    assert selected["route"] == "fail_closed"
    assert selected["decision"] == {"verdict": "fail_closed"}


def test_valid_retry_becomes_authoritative_domain_result():
    first=validate_review_output("bad")
    retry=validate_review_output('{"verdict":"approve","secrets":false,"blocking":[]}')
    out=select_review_decision({"route":"agent","request_changes_count":0},first,retry)
    assert out["route"] == "publish"
    assert out["decision"]["verdict"] == "approve"


def test_second_invalid_result_is_terminal_fail_closed():
    first=validate_review_output("bad one")
    retry=validate_review_output("bad two")
    out=select_review_decision({"route":"agent"},first,retry)
    assert out["route"] == "fail_closed"
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


def test_structured_review_does_not_fall_back_to_a_different_reviewer_for_evidence():
    from lokay.organ.review_boundary import handle_review_boundary

    out = handle_review_boundary(
        "validate_evidence_review", {},
        {"select_pr_review": {"route": "evidence"}},
        {"repo": "a/b", "pr_number": 7, "branch": "b", "live": True},
    )

    assert out["route"] == "fail_closed"
    assert out["reason"] == "structured_evidence_review_unsupported"


def test_live_review_validation_fails_closed_when_plugin_request_is_missing():
    from lokay.organ.review_boundary import handle_review_boundary

    up = {
        "collect_pr_review_evidence": {"evidence": {"task": {"number": 42}}},
        "resolve_sha_review": {"route": "agent"},
        "pr_review_agent": {"result": {}},
    }
    out = handle_review_boundary(
        "validate_pr_review", {}, up,
        {"repo": "a/b", "pr_number": 7, "branch": "b", "live": True},
    )

    assert out["route"] == "fail_closed"
    assert out["reason"] == "review_request_missing"


def test_live_review_validation_keeps_classified_plugin_error():
    from lokay.organ.review_boundary import handle_review_boundary

    up = {
        "collect_pr_review_evidence": {"evidence": {"task": {"number": 42}}},
        "resolve_sha_review": {"route": "agent"},
        "pr_review_agent": {"plugin_error": "ocr_exited_unsuccessfully"},
    }
    out = handle_review_boundary(
        "validate_pr_review", {}, up,
        {"repo": "a/b", "pr_number": 7, "branch": "b", "live": True},
    )

    assert out["route"] == "fail_closed"
    assert out["reason"] == "ocr_exited_unsuccessfully"
    assert out["reason"] != "review_plugin_failed"


def test_live_review_validation_classifies_host_not_json_as_ocr_code():
    from lokay.organ.review_boundary import handle_review_boundary

    up = {
        "collect_pr_review_evidence": {"evidence": {"task": {"number": 42}}},
        "resolve_sha_review": {"route": "agent"},
        "pr_review_agent": {
            "plugin_error": "review plugin did not return one JSON envelope",
        },
    }
    out = handle_review_boundary(
        "validate_pr_review", {}, up,
        {"repo": "mikolaj92/splot", "pr_number": 56, "branch": "b", "live": True},
    )

    assert out["route"] == "fail_closed"
    assert out["reason"] == "ocr_output_not_json"
    assert out["reason"] != "review_plugin_failed"


def test_fail_closed_marker_on_current_sha_reinvokes_agent():
    from lokay.pr_review import format_review_marker
    from lokay.review_boundary import resolve_structured_sha_review

    head = "a" * 40
    evidence = {
        "head_sha": head,
        "comments": [
            "Lokay LLM PR review failed closed: ocr_contract_rejected\n"
            + format_review_marker(head_sha=head, verdict="fail_closed", merge_ok=False)
        ],
    }

    out = resolve_structured_sha_review(evidence)

    assert out["route"] == "agent"
    assert out.get("decision", {}).get("verdict") != "fail_closed"
    assert out.get("merge_ok") is not True


def test_cached_fail_closed_is_authoritative_for_this_sha():
    from lokay.review_boundary import select_structured_review

    head = "a" * 40
    selected = select_structured_review(
        {
            "route": "cached",
            "head_sha": head,
            "decision": {"verdict": "fail_closed"},
            "merge_ok": False,
        },
        {},
    )

    assert selected["route"] == "cached"
    assert selected["decision"]["verdict"] == "fail_closed"
    assert selected["merge_ok"] is False


def test_policy_approval_skips_agent_results():
    out=select_review_decision({"route":"policy","decision":{"verdict":"approve"},"merge_ok":True},{"reason":"condition_not_met"},{"reason":"condition_not_met"})
    assert out["route"] == "policy" and out["decision"]["verdict"] == "approve"


def test_needs_evidence_routes_one_closed_collector_round():
    first=validate_review_output('{"verdict":"needs_evidence","evidence_kind":"diff_tail"}')
    selected=select_review_decision({"route":"agent","request_changes_count":2},first,{})
    assert selected["route"] == "evidence"
    assert selected["decision"]["evidence_kind"] == "diff_tail"
    validation=validate_review_output('{"verdict":"approve"}')
    evidence_selected=select_evidence_review(selected,validation)
    final=finalize_review_selection(selected,evidence_selected)
    assert final["route"] == "publish" and final["decision"]["verdict"] == "approve"
    assert final["request_changes_count"] == 2


def test_second_evidence_request_is_terminal_fail_closed():
    selected={"route":"evidence","decision":{"verdict":"needs_evidence","evidence_kind":"changed_files"}}
    validation=validate_review_output('{"verdict":"needs_evidence","evidence_kind":"commit_summary"}')
    out=select_evidence_review(selected,validation)
    assert out["route"] == "fail_closed"
    assert out["decision"] == {"verdict":"fail_closed"}


def test_invalid_evidence_kind_is_rejected_before_routing():
    out=validate_review_output('{"verdict":"needs_evidence","evidence_kind":"arbitrary_shell"}')
    assert out["route"] == "retry"
    assert "evidence_kind" in out["validation_error"]
