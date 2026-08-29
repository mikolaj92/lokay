from lokay.proc.select_next_pr import select
from lokay.proc.summarize_pr_triage_department import summarize


def test_empty_list_is_none() -> None:
    assert select({"ok": True, "prs": []}) == {
        "ok": True,
        "route": "none",
        "reason": "no_open_pr",
    }


def test_first_mill_pr_is_picked() -> None:
    out = select(
        {
            "ok": True,
            "prs": [
                {
                    "repo": "o/r",
                    "pr": 9,
                    "title": "x",
                    "branch": "ai/fix/9-x",
                }
            ],
        }
    )
    assert out["route"] == "pr" and out["pr"] == 9 and out["branch"] == "ai/fix/9-x"


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
                },
            ],
        }
    )
    assert out["route"] == "pr" and out["pr"] == 2


def test_summarize_empty_skip() -> None:
    picked = {"ok": True, "route": "none", "reason": "no_open_pr"}
    out = summarize(picked, {}, {"verdict": "none"})
    assert out["ok"] is True
    assert out["department"] == "pr_triage"
    assert out["route"] == "none"
    assert out["repair_started"] is False
