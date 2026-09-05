from lokay.proc.summarize_issue_triage import summarize as issue_triage
from lokay.proc.summarize_issue_split import summarize as issue_split
from lokay.proc.summarize_pr_triage import summarize as pr_triage


def test_issue_triage_terminal_is_authoritative():
    out = issue_triage(
        final={"decision": {"verdict": "ready", "reason": "ready"}},
        ready={"applied": True},
        skip={},
        blocked={},
        close={},
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
        receipt={"confirmed": True, "receipt": {"receipt_digest": "sha256:r"}},
    )["result"]
    assert out["merged"] is True and out["closed_issue"] == 7
    assert out["delivery_confirmed"] is True


def test_pr_triage_merge_without_confirmed_receipt_is_not_done():
    out = pr_triage(
        review={"decision": {"verdict": "approve"}},
        repair={},
        repair_manual={},
        manual={},
        merge={"merged": True},
        close={"issue": 7},
        receipt={"confirmed": False, "reason": "delivery_confirmation_incomplete"},
    )["result"]
    assert out["merged"] is True
    assert out["delivery_confirmed"] is False
    assert out["reason"] == "delivery_confirmation_incomplete"


def test_pr_triage_request_changes_leaves_repair_verdict():
    out = pr_triage(
        review={"decision": {"verdict": "request_changes"}},
        repair={},
        repair_manual={},
        manual={},
        merge={},
        close={},
        outcome={"route": "repair", "reason": "review_requested_changes"},
    )["result"]
    assert out["skipped"] and out["repairable"] is True
    assert "repaired" not in out


def test_pr_triage_wait_terminal_does_not_fail():
    out = pr_triage(
        review={},
        repair={},
        repair_manual={},
        manual={},
        merge={},
        close={},
        outcome={"route": "wait", "reason": "checks_pending", "waiting": True},
    )["result"]
    assert out["skipped"] and out["waiting"] and out["reason"] == "checks_pending"


def test_self_repair_terminal_releases_gate():
    from lokay.proc.summarize_self_repair import summarize

    out = summarize(
        preflight={"validated": True, "restart_required": True, "commit": "abc"},
        push={},
        activate={},
        close={"closed": True},
    )["result"]
    assert (
        out.get("ok", True) is not False
        and out["gate_released"] is True
        and out["incident_closed"] is True
    )


def test_self_repair_dirty_activation_preserves_published_result():
    from lokay.proc.summarize_self_repair import summarize

    out = summarize(
        preflight={},
        push={"commit": "abc"},
        activate={"published": True, "reason": "dirty_tree"},
        close={},
    )["result"]
    assert out["ok"] is True and out["reason"] == "published_push_kept_dirty_tree"
