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


def test_pr_triage_request_changes_preserves_complete_repair_handoff():
    task = {"repo": "o/r", "type": "Issue", "state": "OPEN", "number": 7}
    findings = [{"path": "src/a.py", "start_line": 1, "end_line": 1, "content": "fix"}]
    head = "a" * 40
    task_digest = "b" * 64
    result_digest = "c" * 64
    out = pr_triage(
        review={"decision": {
            "verdict": "request_changes", "task": task, "findings": findings,
            "reviewed_head_sha": head,
            "task_identity_sha256": task_digest, "review_result_sha256": result_digest,
        }},
        repair={},
        repair_manual={},
        manual={},
        merge={},
        close={},
        outcome={
            "route": "repair", "repair_kind": "review",
            "reason": "review_requested_changes", "task": task,
            "findings": findings, "reviewed_head_sha": head,
            "repair_start_head_sha": head,
            "task_identity_sha256": task_digest,
            "review_result_sha256": result_digest,
        },
    )["result"]
    assert out["skipped"] and out["repairable"] is True
    assert out["repair_kind"] == "review"
    assert out["task"] == task and out["findings"] == findings
    assert out["reviewed_head_sha"] == out["repair_start_head_sha"] == head
    assert out["task_identity_sha256"] == task_digest
    assert out["review_result_sha256"] == result_digest
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
