from lokay.proc.select_next_pr import select
from lokay.proc.summarize_pr_triage_department import summarize


def _listed(*prs):
    rows = list(prs)
    return {"ok": True, "prs": rows, "count": len(rows)}


def _pr(repo: str, number: int, sha: str) -> dict:
    return {
        "repo": repo,
        "pr": number,
        "title": f"{repo}#{number}",
        "branch": f"ai/fix/{number}-x",
        "head_sha": sha,
    }


KIT_39 = _pr("mikolaj92/OpenAPITransportKit", 39, "f654e881")
VIBE_30 = _pr("mikolaj92/VibeFront", 30, "abc111")
SPLOT_55 = _pr("mikolaj92/splot", 55, "def222")


def test_empty_list_is_none() -> None:
    assert select({"ok": True, "prs": []}) == {
        "ok": True,
        "route": "none",
        "reason": "no_open_pr",
    }


def test_first_lokay_pr_is_picked() -> None:
    out = select(
        {
            "ok": True,
            "prs": [
                {
                    "repo": "o/r",
                    "pr": 9,
                    "title": "x",
                    "branch": "ai/fix/9-x",
                    "head_sha": "abc",
                }
            ],
        }
    )
    assert out["route"] == "pr" and out["pr"] == 9 and out["branch"] == "ai/fix/9-x"
    assert out["head_sha"] == "abc"
    assert out["leftover"] == 0
    assert out["leftover_prs"] == []


def test_row_without_branch_is_skipped() -> None:
    out = select(
        {
            "ok": True,
            "prs": [
                {"repo": "o/r", "pr": 1, "title": "no-branch"},
                {
                    "repo": "o/r",
                    "pr": 2,
                    "title": "ok",
                    "branch": "ai/fix/2-x",
                    "head_sha": "def",
                },
            ],
        }
    )
    assert out["route"] == "pr" and out["pr"] == 2
    assert out["head_sha"] == "def"


def test_consumed_fail_closed_sha_walks_to_next_pr() -> None:
    last = {
        "leftover_prs": [VIBE_30, SPLOT_55],
        "skipped_pr": 39,
        "skipped_repo": "mikolaj92/OpenAPITransportKit",
        "skipped_head_sha": "f654e881",
    }
    out = select(_listed(KIT_39, VIBE_30, SPLOT_55), last=last)
    assert out["route"] == "pr"
    assert out["repo"] == "mikolaj92/VibeFront"
    assert out["pr"] == 30
    assert out["head_sha"] == "abc111"
    assert out["leftover"] == 1
    assert [row["pr"] for row in out["leftover_prs"]] == [55]


def test_consumed_empty_leftover_does_not_keep_same_sha() -> None:
    last = {
        "leftover": 0,
        "leftover_prs": [],
        "skipped_pr": 39,
        "skipped_repo": "mikolaj92/OpenAPITransportKit",
        "skipped_head_sha": "f654e881",
    }
    out = select(_listed(KIT_39, VIBE_30, SPLOT_55), last=last)
    assert out["route"] == "pr"
    assert out["pr"] == 30
    assert [row["pr"] for row in out["leftover_prs"]] == [55]


def test_new_sha_on_same_pr_is_a_new_identity() -> None:
    last = {
        "leftover_prs": [VIBE_30],
        "skipped_pr": 39,
        "skipped_repo": "mikolaj92/OpenAPITransportKit",
        "skipped_head_sha": "f654e881",
    }
    listed = _listed(_pr("mikolaj92/OpenAPITransportKit", 39, "newsha99"), VIBE_30)
    out = select(listed, last=last)
    assert out["route"] == "pr"
    assert out["pr"] == 39
    assert out["head_sha"] == "newsha99"


def test_exhausted_consumed_queue_is_none() -> None:
    last = {
        "leftover_prs": [],
        "skipped_pr": 39,
        "skipped_repo": "mikolaj92/OpenAPITransportKit",
        "skipped_head_sha": "f654e881",
    }
    out = select(_listed(KIT_39), last=last)
    assert out["ok"] is True
    assert out["route"] == "none"
    assert out["reason"] == "no_open_pr"
    assert out["leftover"] == 0
    assert out["leftover_prs"] == []
    assert out["skipped_pr"] == 39
    assert out["skipped_repo"] == "mikolaj92/OpenAPITransportKit"
    assert out["skipped_head_sha"] == "f654e881"


def test_summarize_empty_skip() -> None:
    picked = {"ok": True, "route": "none", "reason": "no_open_pr"}
    out = summarize(picked, {}, {"verdict": "none"})
    assert out["ok"] is True
    assert out["department"] == "pr_triage"
    assert out["route"] == "none"
    assert out["repair_started"] is False
    assert out["result"]["verdict"] == "none"
    assert out["result"]["repair_started"] is False


def test_summarize_fail_closed_consumes_and_publishes_leftover() -> None:
    picked = {
        **KIT_39,
        "ok": True,
        "route": "pr",
        "leftover": 2,
        "leftover_prs": [VIBE_30, SPLOT_55],
    }
    out = summarize(
        picked,
        {},
        {
            "route": "fail_closed",
            "verdict": "feedback",
            "reason": "ocr_contract_rejected: review has warnings",
            "repo": KIT_39["repo"],
            "pr": 39,
        },
        {"route": "review"},
    )
    assert out["leftover"] == 2
    assert [row["pr"] for row in out["leftover_prs"]] == [30, 55]
    assert out["skipped_pr"] == 39
    assert out["skipped_repo"] == KIT_39["repo"]
    assert out["skipped_head_sha"] == "f654e881"
    assert out["result"]["leftover_prs"] == out["leftover_prs"]


def test_summarize_exhausted_consumed_queue_keeps_empty_leftover() -> None:
    picked = {
        "ok": True,
        "route": "none",
        "reason": "no_open_pr",
        "leftover": 0,
        "leftover_prs": [],
    }
    out = summarize(picked, {}, {"verdict": "none"})
    assert out["leftover_prs"] == []
    assert out["leftover"] == 0
    assert "skipped_pr" not in out


def test_incomplete_round_robin_keeps_every_sha_and_reaches_repaired_pr() -> None:
    from lokay.organ.pr_triage_department_boundary import handle_pr_triage_department
    from lokay.proc.walk_pr_leftover import identity

    rows = [SPLOT_55, VIBE_30, KIT_39]
    last = {}
    seen = []
    for _ in range(4):
        picked = select(_listed(*rows), last=last)
        seen.append(identity(picked))
        last = handle_pr_triage_department(
            "summarize_pr_triage_department", {"incomplete_retry_position": "tail"},
            {"select_pr_sieve": picked,
             "select_pr_triage_verdict": {"route": "completed", "verdict": "feedback", "reason": "ocr_terminal_incomplete"},
             "reconcile_pr_repair_push": {"route": "review"}}, {},
        )
        assert {identity(row) for row in last["leftover_prs"]} == {identity(row) for row in rows}
        assert "skipped_pr" not in last
    assert seen == [identity(row) for row in [SPLOT_55, VIBE_30, KIT_39, SPLOT_55]]


def test_updated_sha_keeps_existing_leftover_position() -> None:
    updated = {**KIT_39, "head_sha": "repaired"}
    picked = select(_listed(SPLOT_55, updated, VIBE_30), last={"leftover_prs": [KIT_39, VIBE_30, SPLOT_55]})
    assert (picked["pr"], picked["head_sha"]) == (39, "repaired")
    assert [row["pr"] for row in picked["leftover_prs"]] == [30, 55]


def test_summarize_pending_keeps_the_pick_on_leftover() -> None:
    picked = {
        **KIT_39,
        "ok": True,
        "route": "pr",
        "leftover": 1,
        "leftover_prs": [VIBE_30],
    }
    out = summarize(
        picked,
        {"triage": {"waiting": True, "reason": "checks_pending"}},
        {
            "route": "completed",
            "verdict": "feedback",
            "reason": "checks_pending",
            "waiting": True,
            "repo": KIT_39["repo"],
            "pr": 39,
        },
        {"route": "review"},
    )
    assert [row["pr"] for row in out["leftover_prs"]] == [39, 30]
    assert out["leftover"] == 2
    assert "skipped_pr" not in out
