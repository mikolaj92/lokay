from lokay.proc.classify_issue_do import classify
from lokay.proc.select_issue_do import select
from lokay.proc.select_next_issue import select as pick


def test_empty_list_is_none():
    assert pick({"route": "skip", "issues": []})["route"] == "none"


def test_first_issue_is_picked():
    out = pick(
        {"route": "listed", "issues": [{"repo": "o/r", "issue": 2, "title": "x"}]}
    )
    assert out["route"] == "issue" and out["issue"] == 2


def test_ready_means_do():
    picked = {"route": "issue", "repo": "o/r", "issue": 2}
    sito = classify({"route": "completed", "triage": {"result": {"implementable": True}}})
    assert sito["route"] == "ready"
    assert select(picked, sito)["route"] == "do"


def test_not_ready_skips():
    picked = {"route": "issue", "repo": "o/r", "issue": 2}
    sito = classify(
        {"route": "completed", "triage": {"result": {"implementable": False}}}
    )
    assert sito["route"] == "not_ready"
    assert select(picked, sito)["route"] == "skip"


def test_missing_issue_skips_without_fail():
    assert select({"route": "none"}, {})["route"] == "skip"


def test_triage_skip_does_not_fail_the_pass():
    picked = {"route": "issue", "repo": "o/r", "issue": 2}
    sito = classify({})
    assert sito["route"] == "not_ready"
    assert select(picked, sito)["route"] == "skip"


def test_real_triage_envelope_ready_means_do():
    picked = {"route": "issue", "repo": "o/r", "issue": 2}
    sito = classify(
        {
            "route": "completed",
            "triage": {"implementable": True, "decision": {"verdict": "ready"}},
        }
    )
    assert select(picked, sito)["route"] == "do"
