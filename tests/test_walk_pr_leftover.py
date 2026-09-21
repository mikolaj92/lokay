"""PR sieve leftover: skip without merge consumes (repo, pr, sha); pending KEEP."""

import pytest
from fala.conformance import check_payload, exercise_handler
from fala.protocol import ProtocolError, Result

from lokay.proc.walk_pr_leftover import (
    OCCUPANCY_SCHEMA,
    after,
    classify_occupancy,
    consumes,
    identity,
    keep,
    leftover_after,
    queue,
)


def _pr(repo: str, number: int, sha: str, *, title: str = "") -> dict:
    return {
        "repo": repo,
        "pr": number,
        "title": title or f"{repo}#{number}",
        "branch": f"ai/fix/{number}-x",
        "head_sha": sha,
    }


KIT_39 = _pr("mikolaj92/OpenAPITransportKit", 39, "f654e881")
VIBE_30 = _pr("mikolaj92/VibeFront", 30, "abc111")
SPLOT_55 = _pr("mikolaj92/splot", 55, "def222")


def test_identity_is_repo_pr_sha() -> None:
    assert identity(KIT_39) == (
        "mikolaj92/OpenAPITransportKit",
        39,
        "f654e881",
    )
    assert identity({"repo": "o/r", "pr": 1}) == ("o/r", 1, "")
    assert identity({"repo": "o/r"}) is None


def test_fail_closed_and_non_review_skip_consume() -> None:
    assert consumes({"route": "fail_closed", "reason": "ocr_contract_rejected: review has warnings"})
    assert consumes({"route": "fail_closed", "reason": "review has warnings"})
    assert consumes({"route": "completed", "verdict": "feedback", "reason": "ocr_contract_rejected: review has warnings"})
    assert consumes({"route": "completed", "verdict": "feedback", "reason": "review_fail_closed"})
    assert consumes({"route": "completed", "verdict": "merge"})
    assert consumes({"outcome": "merge"})


_INCOMPLETE = (
    "ocr_timed_out",
    "ocr_timed_out: review timed out",
    "ocr_invocation_failed",
    "ocr_exited_unsuccessfully",
    "ocr_output_not_json",
    "ocr_output_not_object",
    "ocr_output_too_large",
    "ocr_budget_exceeded",
    "ocr_terminal_incomplete",
    "ocr_contract_rejected",
    "ocr_contract_rejected: review budget exceeded or unreported",
    "ocr_contract_rejected: review terminal state is not complete",
    "plugin_error",
    "review_plugin_failed",
    "review_failed_closed",
    "review_result_invalid",
    "review_request_missing",
)


@pytest.mark.parametrize("reason", _INCOMPLETE)
def test_incomplete_review_without_json_keeps_the_sha(reason: str) -> None:
    assert not consumes({"route": "fail_closed", "reason": reason})
    assert not consumes({"route": "completed", "verdict": "feedback", "reason": reason})
    assert not consumes({"route": "skip", "reason": reason})


def test_incomplete_ocr_class_is_prefix_not_a_timeout_allowlist() -> None:
    assert not consumes({"route": "fail_closed", "reason": "ocr_new_capacity_code"})
    assert classify_occupancy({"route": "fail_closed", "reason": "ocr_new_capacity_code"}) == {
        "class": "incomplete",
        "keep": True,
    }
    assert classify_occupancy({"route": "fail_closed", "reason": "ocr_contract_rejected"}) == {
        "class": "incomplete",
        "keep": True,
    }
    assert classify_occupancy(
        {"route": "fail_closed", "reason": "ocr_contract_rejected: review has warnings"}
    ) == {
        "class": "complete_reject",
        "keep": False,
    }


def test_pending_checks_keep() -> None:
    assert not consumes({"route": "wait", "reason": "checks_pending", "waiting": True})
    assert not consumes({"route": "completed", "verdict": "feedback", "reason": "checks_pending"})
    assert not consumes({"route": "completed", "reason": "checks_offline", "waiting": True})
    assert not consumes({"route": "wait", "reason": "checks_none_require_checks"})
    assert not consumes({"route": "skip", "reason": "repair_push_recovered"})
    assert not consumes({"route": "completed", "verdict": "feedback", "reason": "merge_disabled"})
    assert not consumes({"route": "completed", "verdict": "repair", "repairable": True})


@pytest.mark.parametrize("reason", ["merge_not_confirmed", "merge_head_unverified", "future_wait_reason"])
def test_structured_wait_keeps_normalized_feedback(reason):
    receipt = {"route": "completed", "verdict": "feedback", "reason": reason}
    assert classify_occupancy({**receipt, "waiting": True}) == {"class": "pending", "keep": True}
    assert consumes({**receipt, "waiting": False})


def test_wait_does_not_override_merge_repair_or_incomplete_class():
    assert classify_occupancy({"waiting": True, "verdict": "merge"}) == {"class": "merge", "keep": False}
    assert classify_occupancy({"waiting": True, "verdict": "repair"}) == {"class": "repair", "keep": True}
    assert classify_occupancy({"waiting": True, "reason": "ocr_timed_out"}) == {"class": "incomplete", "keep": True}


def test_after_skipped_sha_returns_the_rest() -> None:
    listed = [KIT_39, VIBE_30, SPLOT_55]
    rest = after(listed, KIT_39)
    assert [row["pr"] for row in rest] == [30, 55]


def test_keep_starts_at_the_pick() -> None:
    listed = [KIT_39, VIBE_30, SPLOT_55]
    assert [row["pr"] for row in keep(listed, KIT_39)] == [39, 30, 55]


def test_new_sha_is_a_new_identity() -> None:
    listed = [_pr("mikolaj92/OpenAPITransportKit", 39, "newsha99"), VIBE_30]
    rest = after(listed, KIT_39)
    assert [row["pr"] for row in rest] == [39, 30]


def test_queue_walks_leftover_prs_not_the_skipped_sha() -> None:
    listed = [KIT_39, VIBE_30, SPLOT_55]
    last = {
        "leftover_prs": [VIBE_30, SPLOT_55],
        "skipped_pr": 39,
        "skipped_repo": "mikolaj92/OpenAPITransportKit",
        "skipped_head_sha": "f654e881",
    }
    out = queue(listed, last)
    assert [row["pr"] for row in out] == [30, 55]


def test_consumed_empty_leftover_walks_past_skipped_sha() -> None:
    listed = [KIT_39, VIBE_30, SPLOT_55]
    last = {
        "leftover": 0,
        "leftover_prs": [],
        "skipped_pr": 39,
        "skipped_repo": "mikolaj92/OpenAPITransportKit",
        "skipped_head_sha": "f654e881",
    }
    out = queue(listed, last)
    assert [row["pr"] for row in out] == [30, 55]


def test_consumed_sha_does_not_drop_prs_listed_before_it() -> None:
    listed = [VIBE_30, KIT_39, SPLOT_55]
    last = {
        "leftover_prs": [],
        "skipped_pr": 39,
        "skipped_repo": "mikolaj92/OpenAPITransportKit",
        "skipped_head_sha": "f654e881",
    }
    out = queue(listed, last)
    assert [row["pr"] for row in out] == [30, 55]


def test_consumed_only_pr_does_not_wrap_back_to_same_sha() -> None:
    listed = [KIT_39]
    last = {
        "leftover_prs": [],
        "skipped_pr": 39,
        "skipped_repo": "mikolaj92/OpenAPITransportKit",
        "skipped_head_sha": "f654e881",
    }
    assert queue(listed, last) == []


def test_leftover_after_consume_drops_the_pick() -> None:
    picked = {**KIT_39, "route": "pr", "leftover_prs": [VIBE_30, SPLOT_55]}
    rest = leftover_after(
        picked, {"route": "fail_closed", "reason": "ocr_contract_rejected: review has warnings"}
    )
    assert [row["pr"] for row in rest] == [30, 55]


def test_leftover_after_pending_keeps_the_pick() -> None:
    picked = {**KIT_39, "route": "pr", "leftover_prs": [VIBE_30]}
    kept = leftover_after(picked, {"route": "wait", "reason": "checks_pending"})
    assert [row["pr"] for row in kept] == [39, 30]


def test_leftover_after_ocr_timeout_keeps_the_pick() -> None:
    picked = {**KIT_39, "route": "pr", "leftover_prs": [VIBE_30, SPLOT_55]}
    kept = leftover_after(picked, {"route": "fail_closed", "reason": "ocr_timed_out"})
    assert [row["pr"] for row in kept] == [39, 30, 55]


@pytest.mark.parametrize(
    "reason",
    (
        "ocr_invocation_failed",
        "ocr_exited_unsuccessfully",
        "ocr_output_not_json",
        "plugin_error",
        "review_plugin_failed",
    ),
)
def test_leftover_after_incomplete_plugin_keeps_the_pick(reason: str) -> None:
    picked = {**KIT_39, "route": "pr", "leftover_prs": [VIBE_30, SPLOT_55]}
    kept = leftover_after(picked, {"route": "fail_closed", "reason": reason})
    assert [row["pr"] for row in kept] == [39, 30, 55]


def _occupancy_handler(request):
    return Result.from_request(request, payload=classify_occupancy(request.payload))


def test_fala_occupancy_contract_incomplete_keeps() -> None:
    result = exercise_handler(
        _occupancy_handler,
        {"route": "fail_closed", "reason": "ocr_invocation_failed"},
        OCCUPANCY_SCHEMA,
        job="summarize_pr_triage_department",
    )
    assert result.payload == {"class": "incomplete", "keep": True}
    check_payload(result.payload, OCCUPANCY_SCHEMA)


def test_fala_occupancy_contract_complete_reject_consumes() -> None:
    result = exercise_handler(
        _occupancy_handler,
        {"route": "fail_closed", "reason": "ocr_contract_rejected: review has warnings"},
        OCCUPANCY_SCHEMA,
        job="summarize_pr_triage_department",
    )
    assert result.payload == {"class": "complete_reject", "keep": False}
    check_payload(result.payload, OCCUPANCY_SCHEMA)


def test_fala_occupancy_contract_merge_consumes() -> None:
    result = exercise_handler(
        _occupancy_handler,
        {"route": "completed", "verdict": "merge", "outcome": "merge"},
        OCCUPANCY_SCHEMA,
        job="summarize_pr_triage_department",
    )
    assert result.payload["class"] == "merge"
    assert result.payload["keep"] is False
    check_payload(result.payload, OCCUPANCY_SCHEMA)


def test_fala_occupancy_contract_rejects_keep_on_complete_reject() -> None:
    with pytest.raises(ProtocolError):
        check_payload({"class": "complete_reject", "keep": True}, OCCUPANCY_SCHEMA)
    with pytest.raises(ProtocolError):
        check_payload({"class": "incomplete", "keep": False}, OCCUPANCY_SCHEMA)


def test_leftover_queue_is_not_jumped_by_a_new_pr() -> None:
    listed = [KIT_39, VIBE_30, SPLOT_55, _pr("mikolaj92/takt", 42, "ttt444")]
    last = {
        "leftover_prs": [VIBE_30, SPLOT_55],
        "skipped_pr": 39,
        "skipped_repo": "mikolaj92/OpenAPITransportKit",
        "skipped_head_sha": "f654e881",
    }
    out = queue(listed, last)
    assert [row["pr"] for row in out] == [30, 55, 42]
