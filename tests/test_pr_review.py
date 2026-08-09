"""Structured PR review parse + policy."""

import pytest

from lokay.pr_review import (
    PrReviewError,
    parse_review_output,
    should_merge,
    should_repair,
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
