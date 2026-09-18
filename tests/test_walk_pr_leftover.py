"""PR sieve leftover: skip without merge consumes (repo, pr, sha); pending KEEP."""

from lokay.proc.walk_pr_leftover import after, consumes, identity, keep, leftover_after, queue


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
    assert consumes({"route": "fail_closed", "reason": "ocr_contract_rejected"})
    assert consumes({"route": "fail_closed", "reason": "review has warnings"})
    assert consumes({"route": "skip", "reason": "plugin_error"})
    assert consumes({"route": "completed", "verdict": "feedback", "reason": "ocr_contract_rejected"})
    assert consumes({"route": "completed", "verdict": "merge"})
    assert consumes({"outcome": "merge"})


def test_pending_checks_keep() -> None:
    assert not consumes({"route": "wait", "reason": "checks_pending", "waiting": True})
    assert not consumes({"route": "completed", "verdict": "feedback", "reason": "checks_pending"})
    assert not consumes({"route": "completed", "reason": "checks_offline", "waiting": True})
    assert not consumes({"route": "wait", "reason": "checks_none_require_checks"})
    assert not consumes({"route": "skip", "reason": "repair_push_recovered"})
    assert not consumes({"route": "completed", "verdict": "feedback", "reason": "merge_disabled"})
    assert not consumes({"route": "completed", "verdict": "repair", "repairable": True})


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
    rest = leftover_after(picked, {"route": "fail_closed", "reason": "ocr_contract_rejected"})
    assert [row["pr"] for row in rest] == [30, 55]


def test_leftover_after_pending_keeps_the_pick() -> None:
    picked = {**KIT_39, "route": "pr", "leftover_prs": [VIBE_30]}
    kept = leftover_after(picked, {"route": "wait", "reason": "checks_pending"})
    assert [row["pr"] for row in kept] == [39, 30]


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
