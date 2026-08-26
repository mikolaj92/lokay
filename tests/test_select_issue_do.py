from lokay.proc.classify_issue_do import classify
from lokay.proc.select_issue_do import select
from lokay.proc.select_next_issue import select as pick


def test_empty_list_is_none():
    assert pick({"issues": [], "count": 0, "overflow": False})["route"] == "none"


def test_first_issue_is_picked():
    out = pick({"issues": [{"repo": "o/r", "issue": 2, "title": "x"}], "count": 1})
    assert out["route"] == "issue" and out["issue"] == 2


def test_ready_means_do():
    picked = {"route": "issue", "repo": "o/r", "issue": 2}
    triage = {"route": "completed", "triage": {"result": {"implementable": True}}}
    assert classify(triage)["route"] == "ready"
    assert select(picked, triage)["route"] == "do"


def test_not_ready_skips():
    picked = {"route": "issue", "repo": "o/r", "issue": 2}
    triage = {"route": "completed", "triage": {"result": {"implementable": False}}}
    assert classify(triage)["route"] == "not_ready"
    assert select(picked, triage)["route"] == "skip"


def test_missing_issue_skips_without_fail():
    assert select({"route": "none"}, {})["route"] == "skip"


def test_triage_skip_does_not_fail_the_pass():
    picked = {"route": "issue", "repo": "o/r", "issue": 2}
    triage = {}
    assert classify(triage)["route"] == "not_ready"
    assert select(picked, triage)["route"] == "skip"


def test_real_triage_envelope_ready_means_do():
    picked = {"route": "issue", "repo": "o/r", "issue": 2}
    triage = {
        "route": "completed",
        "triage": {"implementable": True, "decision": {"verdict": "ready"}},
    }
    assert select(picked, triage)["route"] == "do"
