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


def test_first_skip_then_second_listed_is_selected():
    listed = _listed(
        {"repo": "mikolaj92/lokay", "issue": 806, "title": "oil"},
        {"repo": "mikolaj92/reviewkit", "issue": 205, "title": "next"},
    )
    first = select(listed)
    assert first["issue"] == 806
    from lokay.proc.select_issue_do import select as select_do

    skipped = select_do(first, {"route": "failed"}, listed)
    assert skipped["ok"] is True
    assert skipped["route"] == "skip"
    assert skipped["reason"] == "triage_not_done"
    assert skipped["leftover"] == 1
    assert skipped["leftover_issues"][0]["issue"] == 205
    second = select(listed, last=skipped)
    assert second["route"] == "issue"
    assert second["issue"] == 205
    assert second["leftover"] == 0


def test_leftover_zero_only_when_list_is_exhausted():
    listed = _listed(
        {"repo": "o/r", "issue": 1},
        {"repo": "o/r", "issue": 2},
        {"repo": "o/r", "issue": 3},
    )
    first = select(listed)
    assert first["leftover"] == 2
    from lokay.proc.select_issue_do import select as select_do

    skip1 = select_do(first, {"route": "failed"}, listed)
    assert skip1["leftover"] == 2
    second = select(listed, last=skip1)
    assert second["issue"] == 2
    assert second["leftover"] == 1
    skip2 = select_do(second, {"route": "failed"}, listed)
    assert skip2["leftover"] == 1
    third = select(listed, last=skip2)
    assert third["issue"] == 3
    assert third["leftover"] == 0


def test_parked_human_stop_already_excluded_by_list_facts():
    listed = _listed({"repo": "o/r", "issue": 9, "title": "open", "labels": []})
    out = select(listed)
    assert out["route"] == "issue"
    assert out["issue"] == 9
    assert out["leftover"] == 0
