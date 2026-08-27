from lokay.proc.classify_issue_do import classify
from lokay.proc.select_issue_do import select

PICKED = {"route": "issue", "repo": "o/r", "issue": 2}


def test_triage_implementable_means_do():
    triage = {"route": "completed", "triage": {"implementable": True}}
    assert classify(triage)["route"] == "ready"
    assert select(PICKED, triage) == {
        "ok": True,
        "route": "do",
        "repo": "o/r",
        "issue": 2,
        "leftover": 0,
        "leftover_issues": [],
    }


def test_result_implementable_means_do():
    triage = {"route": "completed", "triage": {"result": {"implementable": True}}}
    assert classify(triage)["implementable"] is True
    assert select(PICKED, triage)["route"] == "do"


def test_decision_verdict_ready_means_do():
    triage = {"route": "completed", "triage": {"decision": {"verdict": "ready"}}}
    assert classify(triage)["route"] == "ready"
    assert select(PICKED, triage)["route"] == "do"


def test_result_decision_verdict_ready_means_do():
    triage = {
        "route": "completed",
        "triage": {"result": {"decision": {"verdict": "ready"}}},
    }
    assert classify(triage)["route"] == "ready"
    assert select(PICKED, triage)["route"] == "do"


def test_not_implementable_skips_without_fail():
    triage = {"route": "completed", "triage": {"result": {"implementable": False}}}
    out = select(PICKED, triage)
    assert classify(triage)["route"] == "not_ready"
    assert out["ok"] is True
    assert out["route"] == "skip"
    assert out["reason"] == "sito_nie_robic"


def test_missing_issue_skips_without_fail():
    out = select({"route": "none"}, {})
    assert out["ok"] is True
    assert out["route"] == "skip"
    assert out["reason"] == "no_issue"


def test_triage_not_completed_skips_without_fail():
    out = select(PICKED, {"route": "failed"})
    assert out["ok"] is True
    assert out["route"] == "skip"
    assert out["reason"] == "triage_not_done"


def test_skipped_triage_envelope_does_not_fail_the_pass():
    out = select(PICKED, {})
    assert classify({})["route"] == "not_ready"
    assert out["ok"] is True
    assert out["route"] == "skip"


def test_labels_are_not_a_gate():
    unlabeled = {**PICKED, "labels": []}
    labeled = {**PICKED, "labels": ["work:ready", "ai:ready"]}
    ready = {"route": "completed", "triage": {"implementable": True}}
    closed = {"route": "completed", "triage": {"implementable": False}}
    assert select(unlabeled, ready)["route"] == "do"
    assert select(labeled, ready)["route"] == "do"
    assert select(unlabeled, closed)["route"] == "skip"
    assert select(labeled, closed)["route"] == "do"


def test_leftover_does_not_become_a_second_implement():
    picked = {**PICKED, "leftover": 4}
    triage = {"route": "completed", "triage": {"implementable": True}}
    out = select(picked, triage)
    assert out["ok"] is True
    assert out["route"] == "do"
    assert out["issue"] == 2
    assert out["leftover"] == 4
    assert out["leftover_issues"] == []


def test_ready_leftover_sito_miss_is_do():
    picked = {
        **PICKED,
        "repo": "Temida/Temida",
        "issue": 5001,
        "labels": ["ai:ready", "work:ready"],
        "leftover": 2,
        "leftover_issues": [
            {"repo": "Temida/Temida", "issue": 4999, "labels": ["ai:ready", "work:ready"]},
            {"repo": "Temida/Temida", "issue": 4997, "labels": ["ai:ready", "work:ready"]},
        ],
    }
    listed = {
        "issues": [
            {
                "repo": "Temida/Temida",
                "issue": 5001,
                "labels": ["ai:ready", "work:ready"],
            },
            {
                "repo": "Temida/Temida",
                "issue": 4999,
                "labels": ["ai:ready", "work:ready"],
            },
            {
                "repo": "Temida/Temida",
                "issue": 4997,
                "labels": ["ai:ready", "work:ready"],
            },
        ]
    }
    out = select(picked, {"route": "not_ready", "reason": "triage_not_done"}, listed)
    assert out["route"] == "do"
    assert out["issue"] == 5001
    assert out["leftover"] == 3
    assert out["leftover_issues"][0]["issue"] == 5001
