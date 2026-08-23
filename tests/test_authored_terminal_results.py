from lokay.proc.summarize_issue_triage import summarize as issue_triage
from lokay.proc.summarize_issue_split import summarize as issue_split
from lokay.proc.summarize_pr_triage import summarize as pr_triage


def test_issue_triage_terminal_is_authoritative():
    out = issue_triage(
        final={"decision": {"verdict": "ready", "reason": "ready"}},
        ready={"applied": True},
        blocked={},
        close={},
        split={},
        manual={},
    )["result"]
    assert out["applied"] and out["implementable"] and not out["skipped"]


def test_issue_split_terminal_is_authoritative():
    out = issue_split(
        plan={"route": "children", "plan": {"children": []}},
        comment={"children": [{"number": 2}]},
        close={"applied": True},
        manual={},
    )["result"]
    assert out["decision"]["verdict"] == "split" and out["children"] == [{"number": 2}]


def test_pr_triage_approve_terminal_is_authoritative():
    out = pr_triage(
        review={"decision": {"verdict": "approve"}},
        repair={},
        repair_manual={},
        manual={},
        merge={"merged": True},
        close={"issue": 7},
    )["result"]
    assert out["merged"] is True and out["closed_issue"] == 7


def test_pr_triage_request_changes_preserves_subflow_result():
    out = pr_triage(
        review={"decision": {"verdict": "request_changes"}},
        repair={"ok": True, "repaired": True},
        repair_manual={},
        manual={},
        merge={},
        close={},
    )["result"]
    assert out["skipped"] and out["repaired"]
