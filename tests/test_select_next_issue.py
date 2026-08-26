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
