from types import SimpleNamespace

from lokay.pr_review import PrReviewDecision
from lokay.review_style import style_review_comment


def test_style_is_applied_only_to_human_text_and_preserves_marker():
    decision = PrReviewDecision(
        verdict="request_changes",
        blocking=("Empty id can be submitted.",),
        summary="The save flow accepts a placeholder.",
    )
    calls = []

    def stylist(text: str, target: str) -> str:
        calls.append((text, target))
        return "Could we guard the loaded value before saving?"

    body = style_review_comment(
        decision,
        head_sha="abc",
        merge_ok=False,
        escalated=False,
        target="en+kofte",
        stylist=stylist,
    )
    assert body.startswith("<!-- lokay-review head=abc verdict=request_changes merge_ok=0 -->")
    assert "Could we guard" in body
    assert calls[0][1] == "en+kofte"
    assert "verdict=request_changes" not in calls[0][0]


def test_style_failure_falls_back_to_neutral_comment():
    decision = PrReviewDecision(verdict="approve", summary="Ready.")

    def broken(_text: str, _target: str) -> str:
        raise RuntimeError("offline")

    body = style_review_comment(
        decision,
        head_sha="abc",
        merge_ok=True,
        escalated=False,
        target="en+kofte",
        stylist=broken,
    )
    assert "Ready." in body
    assert "verdict=approve merge_ok=1" in body


def test_empty_style_uses_neutral_comment_without_stylist():
    decision = PrReviewDecision(verdict="approve", summary="Ready.")
    body = style_review_comment(
        decision,
        head_sha="abc",
        merge_ok=True,
        escalated=False,
        target="",
        stylist=lambda *_: (_ for _ in ()).throw(AssertionError("not called")),
    )
    assert "Ready." in body
