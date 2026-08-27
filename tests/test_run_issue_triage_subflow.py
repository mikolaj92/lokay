from lokay.proc.classify_issue_do import classify
from lokay.proc.run_issue_triage_subflow import failed, run
from lokay.proc.select_issue_do import select as select_do
from lokay.proc.select_next_issue import select as pick
from lokay.proc.summarize_issues import envelope


TARGET = {"ok": True, "route": "issue", "repo": "Temida/Temida", "issue": 5005}


def test_systemexit_33_is_failed_not_completed(monkeypatch):
    def boom(**_k):
        raise SystemExit(33)

    monkeypatch.setattr("lokay.proc.run_issue_triage_subflow.run_path", boom)
    out = run(TARGET, config_path=None)
    assert out["ok"] is True
    assert out["route"] == "failed"
    assert out["issue"] == 5005
    assert "33" in str(out["error"])
    assert classify(out)["route"] == "not_ready"
    assert classify(out)["reason"] == "triage_not_done"


def test_failed_keeps_route_last():
    out = failed({**TARGET, "route": "issue"}, SystemExit(33))
    assert out["route"] == "failed"
    assert out["ok"] is True


def test_failed_leftover_walk_same_pass_keeps_count_12():
    listed = {
        "ok": True,
        "issues": [{"repo": "o/r", "issue": n} for n in range(1, 14)],
        "count": 13,
        "overflow": False,
    }
    picked = pick(listed)
    assert picked["issue"] == 1
    assert picked["leftover"] == 12
    triage = failed(picked, SystemExit(33))
    do = select_do(picked, triage, listed)
    assert do["route"] == "skip"
    assert do["reason"] == "triage_not_done"
    assert do["leftover"] == 13
    assert do["leftover_issues"][0]["issue"] == 1
    receipt = envelope(picked, do, {})
    assert receipt["result"]["leftover"] == 13
    assert len(receipt["result"]["leftover_issues"]) == 13
    assert receipt["result"]["route"] == "skip"
