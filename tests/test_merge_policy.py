"""Hermetic merge decision matrix for trusted auto-merge."""

from __future__ import annotations

import pytest

from lokay.merge_policy import decide_auto_merge
from lokay.pr_review import (
    coerce_soft_nits,
    parse_review_output,
    should_label_needs_review,
    should_merge,
)


def _review(
    verdict: str,
    *,
    merge_ok: bool | None = None,
    secrets: bool = False,
    escalated: bool = False,
    skipped: bool = False,
    reason: str = "",
    blocking: list[str] | None = None,
    nits: list[str] | None = None,
) -> dict:
    if merge_ok is None:
        merge_ok = verdict == "approve" and not secrets and not escalated
    decision = {
        "verdict": verdict,
        "secrets": secrets,
        "blocking": blocking or [],
        "nits": nits or [],
        "scope_ok": True,
        "tests_adequate": True,
    }
    out: dict = {"merge_ok": merge_ok, "decision": decision, "escalated": escalated}
    if skipped:
        out["skipped"] = True
    if reason:
        out["reason"] = reason
    return out


@pytest.mark.parametrize(
    "kwargs,action,reason",
    [
        (
            {
                "merge_enabled": False,
                "checks": {"status": "passed", "merge_ok": True},
                "review": _review("approve"),
            },
            "disabled",
            "merge_disabled",
        ),
        (
            {
                "merge_enabled": True,
                "checks": {"status": "pending"},
                "review": _review("approve"),
            },
            "waiting",
            "checks_pending",
        ),
        (
            {
                "merge_enabled": True,
                "require_checks": True,
                "checks": {"status": "none", "merge_ok": False},
                "review": _review("approve"),
            },
            "waiting",
            "checks_none_require_checks",
        ),
        (
            {
                "merge_enabled": True,
                "checks": {"status": "failed"},
                "review": _review("approve"),
            },
            "repair",
            "checks_failed",
        ),
        (
            {
                "merge_enabled": True,
                "checks": {"status": "passed", "merge_ok": True},
                "review": _review("approve"),
            },
            "merge",
            "approve_green",
        ),
        (
            {
                "merge_enabled": True,
                "checks": {"status": "passed", "green": True},
                "review": _review("approve", secrets=True, merge_ok=False),
            },
            "blocked",
            "secrets",
        ),
        (
            {
                "merge_enabled": True,
                "checks": {"status": "passed", "merge_ok": True},
                "review": _review("needs_human", merge_ok=False),
            },
            "blocked",
            "needs_human",
        ),
        (
            {
                "merge_enabled": True,
                "checks": {"status": "passed", "merge_ok": True},
                "review": _review(
                    "request_changes",
                    merge_ok=False,
                    escalated=True,
                    reason="llm_review_escalated_needs_review",
                ),
            },
            "blocked",
            "llm_review_escalated_needs_review",
        ),
        (
            {
                "merge_enabled": True,
                "checks": {"status": "passed", "merge_ok": True},
                "review": _review("request_changes", merge_ok=False),
            },
            "repair",
            "llm_review_requested_changes",
        ),
        (
            {
                "merge_enabled": True,
                "checks": {"status": "passed", "merge_ok": True},
                "pr_labels": ["ai:generated", "ai:needs-review"],
                "review": _review("approve"),
            },
            "blocked",
            "ai_needs_review_label",
        ),
        (
            {
                "merge_enabled": True,
                "require_llm_review": False,
                "checks": {"status": "none", "merge_ok": True},
                "review": {
                    "skipped": True,
                    "reason": "llm_review_not_required",
                    "merge_ok": True,
                },
            },
            "merge",
            "approve_green",
        ),
        (
            {
                "merge_enabled": True,
                "checks": {"status": "passed", "merge_ok": True},
                "review": {
                    "skipped": True,
                    "reason": "invalid_review_json",
                    "merge_ok": False,
                },
            },
            "blocked",
            "invalid_review_json",
        ),
    ],
)
def test_decide_auto_merge_matrix(kwargs, action, reason):
    base = {
        "merge_enabled": True,
        "require_checks": False,
        "require_llm_review": True,
        "checks": None,
        "review": None,
        "pr_labels": None,
    }
    base.update(kwargs)
    got = decide_auto_merge(**base)
    assert got.action == action
    assert got.reason == reason
    if action == "merge":
        assert got.merge_ok is True
    if action == "waiting":
        assert got.waiting is True
    if reason in {"secrets", "needs_human", "llm_review_escalated_needs_review", "ai_needs_review_label"}:
        assert got.needs_review is True
    if action == "repair" and reason == "llm_review_requested_changes":
        assert got.repairable is True


def test_approve_with_soft_nits_still_merges():
    d = coerce_soft_nits(
        parse_review_output(
            '{"verdict":"approve","secrets":false,"blocking":[],'
            '"nits":["typo in README"],"scope_ok":true,"tests_adequate":true,'
            '"summary":"ok"}'
        )
    )
    assert d.verdict == "approve"
    assert should_merge(d) is True
    assert should_label_needs_review(d) is False
    got = decide_auto_merge(
        merge_enabled=True,
        checks={"status": "passed", "merge_ok": True},
        review=_review("approve", nits=["typo in README"]),
    )
    assert got.action == "merge"


def test_request_changes_soft_nits_coerced_to_approve():
    d = coerce_soft_nits(
        parse_review_output(
            '{"verdict":"request_changes","risk":"low","secrets":false,'
            '"blocking":[],"nits":["docs wording"],"scope_ok":true,'
            '"tests_adequate":true,"summary":"nit"}'
        )
    )
    assert d.verdict == "approve"
    assert should_merge(d) is True
    assert should_label_needs_review(d) is False


def test_needs_human_low_risk_soft_nits_coerced():
    d = coerce_soft_nits(
        parse_review_output(
            '{"verdict":"needs_human","risk":"low","secrets":false,'
            '"blocking":[],"nits":["comment polish"],"scope_ok":true,'
            '"tests_adequate":true,"summary":"nit"}'
        )
    )
    assert d.verdict == "approve"
    assert should_label_needs_review(d) is False


def test_needs_human_product_judgment_not_coerced():
    d = coerce_soft_nits(
        parse_review_output(
            '{"verdict":"needs_human","risk":"high","secrets":false,'
            '"blocking":[],"nits":[],"summary":"product call"}'
        )
    )
    assert d.verdict == "needs_human"
    assert should_label_needs_review(d) is True
    assert should_merge(d) is False


def test_secrets_always_needs_review_label():
    d = parse_review_output(
        '{"verdict":"approve","secrets":true,"summary":"key"}'
    )
    assert should_label_needs_review(d) is True
    assert should_label_needs_review(d, escalated=False) is True


def test_escalated_cap_needs_review_label():
    d = parse_review_output(
        '{"verdict":"request_changes","secrets":false,"blocking":["x"]}'
    )
    assert should_label_needs_review(d, escalated=True) is True
    assert should_label_needs_review(d, escalated=False) is False
