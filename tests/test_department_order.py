"""PR triage waits for the executor body to finish, not merely to be selected."""

from lokay.organ.departments_boundary import handle_departments


def test_pr_triage_waits_while_executor_body_has_not_finished():
    up = {
        "select_executor_department": {"route": "run"},
        "select_self_repair_department": {"route": "skip"},
    }
    out = handle_departments("select_pr_triage_department", {}, up, {})
    assert out is not None
    assert out["route"] == "skip"
    assert out["reason"] == "executor_not_finished"


def test_pr_triage_runs_after_executor_body_succeeds():
    up = {
        "select_executor_department": {"route": "run"},
        "run_executor_department": {"ok": True, "route": "done"},
    }
    out = handle_departments("select_pr_triage_department", {}, up, {})
    assert out is not None
    assert out["route"] == "run"


def test_pr_triage_runs_when_executor_was_not_selected():
    up = {"select_executor_department": {"route": "skip", "reason": "executor_disabled"}}
    out = handle_departments("select_pr_triage_department", {}, up, {})
    assert out is not None
    assert out["route"] == "run"


def test_pr_triage_does_not_run_after_executor_body_fails():
    up = {
        "select_executor_department": {"route": "run"},
        "run_executor_department": {"ok": False, "route": "failed"},
    }
    out = handle_departments("select_pr_triage_department", {}, up, {})
    assert out is not None
    assert out["route"] == "skip"
    assert out["reason"] == "executor_failed"
