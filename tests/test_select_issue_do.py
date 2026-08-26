from lokay.proc.select_issue_do import select
from lokay.proc.select_next_issue import select as pick


def test_empty_list_is_none():
    assert pick({"issues": []})["route"] == "none"


def test_first_issue_is_picked():
    out = pick({"issues": [{"repo": "o/r", "issue": 2, "title": "x"}]})
    assert out["route"] == "issue" and out["issue"] == 2


def test_ready_means_do():
    picked = {"route": "issue", "repo": "o/r", "issue": 2}
    triage = {"route": "completed", "triage": {"result": {"implementable": True}}}
    assert select(picked, triage)["route"] == "do"


def test_not_ready_skips():
    picked = {"route": "issue", "repo": "o/r", "issue": 2}
    triage = {"route": "completed", "triage": {"result": {"implementable": False}}}
    assert select(picked, triage)["route"] == "skip"
