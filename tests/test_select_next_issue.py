from lokay.proc.classify_open_issues import classify
from lokay.proc.select_next_issue import pick, select


def _listed(*issues, overflow=False):
    rows = list(issues)
    return {"issues": rows, "count": len(rows), "overflow": overflow}


def test_empty_list_facts_are_none():
    out = select(_listed())
    assert out["ok"] is True
    assert out["route"] == "none"
    assert out["reason"] == "empty"


def test_overflow_without_rows_is_none():
    out = select(_listed(overflow=True))
    assert out["ok"] is True
    assert out["route"] == "none"
    assert out["reason"] == "overflow"


def test_overflow_with_rows_picks_one():
    out = select(
        _listed(
            {"repo": "o/r", "issue": 9, "title": "x", "labels": []},
            overflow=True,
        )
    )
    assert out["ok"] is True
    assert out["route"] == "issue"
    assert out["issue"] == 9
    assert out["leftover"] == 0


def test_picks_first_and_leaves_leftover():
    out = select(
        _listed(
            {"repo": "o/r", "issue": 2, "title": "a"},
            {"repo": "o/r", "issue": 3, "title": "b"},
        )
    )
    assert out["route"] == "issue"
    assert out["issue"] == 2
    assert out["leftover"] == 1
    assert out["title"] == "a"


def test_one_issue_leftover_is_zero():
    out = select(_listed({"repo": "o/r", "issue": 4, "title": "solo"}))
    assert out["route"] == "issue"
    assert out["issue"] == 4
    assert out["leftover"] == 0


def test_labels_are_not_a_gate():
    out = select(
        _listed(
            {"repo": "o/r", "issue": 7, "title": "plain", "labels": []},
            {"repo": "o/r", "issue": 8, "title": "ready", "labels": ["work:ready", "ai:ready"]},
        )
    )
    assert out["route"] == "issue"
    assert out["issue"] == 7
    assert out["labels"] == []
    assert out["leftover"] == 1


def test_classified_skip_is_none_not_error():
    out = pick({"route": "skip", "reason": "overflow", "skipped": True})
    assert out["ok"] is True
    assert out["route"] == "none"
    assert out["reason"] == "overflow"


def test_select_composes_classify_then_pick():
    listed = _listed({"repo": "o/r", "issue": 2, "title": "a"})
    assert classify(listed)["route"] == "listed"
    assert select(listed) == pick(classify(listed))


def test_row_cannot_overwrite_route():
    out = select(_listed({"repo": "o/r", "issue": 1, "route": "skip", "ok": False}))
    assert out["ok"] is True
    assert out["route"] == "issue"
    assert out["issue"] == 1


def test_does_not_pick_lokay_oil_as_the_product_slot():
    listed = _listed(
        {"repo": "mikolaj92/lokay", "issue": 848, "title": "oil"},
        {"repo": "Temida/Temida", "issue": 5001, "title": "product"},
    )
    first = select(listed)
    assert first["route"] == "issue"
    assert first["repo"] == "Temida/Temida"
    assert first["issue"] == 5001
    leftover = {
        "leftover": 2,
        "leftover_issues": [
            {"repo": "mikolaj92/lokay", "issue": 848},
            {"repo": "Temida/Temida", "issue": 5001},
        ],
    }
    walked = select(listed, last=leftover)
    assert walked["repo"] == "Temida/Temida"
    assert walked["issue"] == 5001


def test_sito_miss_keeps_leftover_and_the_first_row():
    listed = _listed(
        {"repo": "o/r", "issue": 1},
        {"repo": "o/r", "issue": 2},
        {"repo": "o/r", "issue": 3},
    )
    first = select(listed)
    assert first["issue"] == 1
    assert first["leftover"] == 2
    from lokay.proc.select_issue_do import select as select_do

    skipped = select_do(first, {"route": "failed"}, listed)
    assert skipped["ok"] is True
    assert skipped["route"] == "skip"
    assert skipped["reason"] == "triage_not_done"
    assert skipped["leftover"] == 3
    assert skipped["leftover_issues"][0]["issue"] == 1
    second = select(listed, last=skipped)
    assert second["route"] == "issue"
    assert second["issue"] == 1
    assert second["leftover"] == 2


def test_authored_skip_consumes_leftover():
    listed = _listed(
        {"repo": "o/r", "issue": 1},
        {"repo": "o/r", "issue": 2},
        {"repo": "o/r", "issue": 3},
    )
    first = select(listed)
    from lokay.proc.select_issue_do import select as select_do

    skipped = select_do(
        first,
        {
            "route": "completed",
            "triage": {"decision": {"verdict": "needs_human"}},
        },
        listed,
    )
    assert skipped["route"] == "skip"
    assert skipped["reason"] == "needs_human"
    assert skipped["leftover"] == 2
    assert skipped["leftover_issues"][0]["issue"] == 2
    second = select(listed, last=skipped)
    assert second["issue"] == 2
    assert second["leftover"] == 1


def test_parked_human_stop_already_excluded_by_list_facts():
    listed = _listed({"repo": "o/r", "issue": 9, "title": "open", "labels": []})
    out = select(listed)
    assert out["route"] == "issue"
    assert out["issue"] == 9
    assert out["leftover"] == 0


def test_takes_empty_and_lokaj_skips_pawel():
    listed = _listed(
        {
            "repo": "Temida/Temida",
            "issue": 1,
            "title": "empty",
            "assignees": [],
        },
        {
            "repo": "Temida/Temida",
            "issue": 2,
            "title": "lokaj",
            "assignees": ["mikolaj92"],
        },
        {
            "repo": "Temida/Temida",
            "issue": 3,
            "title": "pawel",
            "assignees": ["PSyron"],
        },
    )
    first = select(listed)
    assert first["route"] == "issue"
    assert first["issue"] == 1
    assert [row["issue"] for row in first["leftover_issues"]] == [2]
    second = select(listed, last=first)
    assert second["route"] == "issue"
    assert second["issue"] == 2
    assert second["leftover"] == 0
    assert second["leftover_issues"] == []
    third = select(listed, last=second)
    assert third["ok"] is True
    assert third["route"] == "none"
    assert third.get("issue") != 3


def test_skips_leading_pawel_and_takes_empty():
    listed = _listed(
        {
            "repo": "Temida/Temida",
            "issue": 5072,
            "title": "pawel",
            "assignees": ["PSyron"],
        },
        {
            "repo": "Temida/Temida",
            "issue": 1,
            "title": "empty",
            "assignees": [],
        },
    )
    out = select(listed)
    assert out["route"] == "issue"
    assert out["issue"] == 1
    assert out["leftover"] == 0


def test_skips_pawel_beside_lokaj():
    listed = _listed(
        {
            "repo": "Temida/Temida",
            "issue": 5072,
            "title": "shared",
            "assignees": ["PSyron", "mikolaj92"],
        }
    )
    out = select(listed)
    assert out["ok"] is True
    assert out["route"] == "none"
    assert out["reason"] == "foreign_assignee"
