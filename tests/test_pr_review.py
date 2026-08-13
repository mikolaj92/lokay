"""Structured PR review parse + policy."""

import pytest

from lokay.pr_review import (
    PrReviewError,
    build_review_comment_body,
    count_request_changes_reviews,
    decide_review_merge,
    find_review_for_head,
    format_review_marker,
    labels_for_review,
    parse_review_markers,
    parse_review_output,
    should_escalate_request_changes,
    should_merge,
    should_repair,
    review_prompt,
)


def test_parse_plain_json():
    d = parse_review_output(
        '{"verdict":"approve","risk":"low","scope_ok":true,"secrets":false,'
        '"tests_adequate":true,"blocking":[],"nits":[],"summary":"ok"}'
    )
    assert d.verdict == "approve"
    assert should_merge(d) is True


def test_parse_fenced_json():
    text = """Here is my review:
```json
{"verdict": "request_changes", "risk": "medium", "scope_ok": false,
 "secrets": false, "tests_adequate": false,
 "blocking": ["missing tests"], "nits": ["typo"], "summary": "needs work"}
```
"""
    d = parse_review_output(text)
    assert d.verdict == "request_changes"
    assert should_merge(d) is False
    assert "missing tests" in d.blocking


def test_parse_fail_closed_empty():
    with pytest.raises(PrReviewError):
        parse_review_output("")


def test_parse_fail_closed_bad_verdict():
    with pytest.raises(PrReviewError):
        parse_review_output('{"verdict":"lgtm","summary":"nope"}')


def test_should_merge_rejects_secrets():
    d = parse_review_output(
        '{"verdict":"approve","secrets":true,"summary":"has key"}'
    )
    assert should_merge(d) is False


def test_should_merge_rejects_blocking():
    d = parse_review_output(
        '{"verdict":"approve","blocking":["x"],"summary":"x"}'
    )
    assert should_merge(d) is False


def test_needs_human():
    d = parse_review_output(
        '{"verdict":"needs_human","risk":"high","summary":"policy"}'
    )
    assert d.verdict == "needs_human"
    assert should_merge(d) is False


def test_request_changes_is_repairable_without_secrets():
    d = parse_review_output(
        '{"verdict":"request_changes","secrets":false,"blocking":["fix it"]}'
    )
    assert should_repair(d) is True
    assert should_merge(d) is False


def test_request_changes_with_secrets_is_not_repairable():
    d = parse_review_output(
        '{"verdict":"request_changes","secrets":true,"blocking":["key"]}'
    )
    assert should_repair(d) is False


@pytest.mark.parametrize(
    "field", ["scope_ok", "tests_adequate"]
)
def test_approve_rejects_false_safety_field(field):
    d = parse_review_output(f'{{"verdict":"approve","{field}":false}}')
    assert should_merge(d) is False


def test_boolean_strings_fail_closed():
    with pytest.raises(PrReviewError):
        parse_review_output('{"verdict":"approve","secrets":"false"}')


def test_review_prompt_sets_collector_execution_boundary():
    prompt = review_prompt(
        repo="a/b",
        pr_number=7,
        title="collector patch",
        body="",
        head_ref="ai/fix/7-collector",
        diff_text="diff --git a/x.py b/x.py\n",
        checks_text="",
    )
    assert "Collector boundary" in prompt
    assert "must not use Pi or the mill to populate data" in prompt
    assert "wait for collection to finish" in prompt


def test_review_marker_roundtrip_and_head_lookup():
    body = build_review_comment_body(
        parse_review_output(
            '{"verdict":"request_changes","secrets":false,"blocking":["x"],'
            '"summary":"fix"}'
        ),
        head_sha="abcDEF12",
        merge_ok=False,
    )
    markers = parse_review_markers([body])
    assert len(markers) == 1
    assert markers[0]["head_sha"] == "abcdef12"
    assert markers[0]["verdict"] == "request_changes"
    assert find_review_for_head(markers, "ABCDEF12")["merge_ok"] is False


def test_request_changes_escalation_cap():
    assert should_escalate_request_changes(0, max_request_changes=2) is False
    assert should_escalate_request_changes(1, max_request_changes=2) is True
    markers = parse_review_markers(
        [
            format_review_marker(head_sha="a" * 40, verdict="request_changes", merge_ok=False),
            format_review_marker(head_sha="b" * 40, verdict="approve", merge_ok=True),
            format_review_marker(head_sha="c" * 40, verdict="request_changes", merge_ok=False),
        ]
    )
    assert count_request_changes_reviews(markers) == 2
    assert should_escalate_request_changes(2, max_request_changes=2) is True


def test_labels_and_merge_decision_helpers():
    d = parse_review_output(
        '{"verdict":"request_changes","secrets":false,"blocking":["x"]}'
    )
    assert labels_for_review(d, escalated=False) == ["ai:request-changes"]
    assert labels_for_review(d, escalated=True) == ["ai:needs-review"]
    merge_ok, escalated = decide_review_merge(d, 1, max_request_changes=2)
    assert merge_ok is False
    assert escalated is True
