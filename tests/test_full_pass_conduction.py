"""End-to-end integration test of factory pass conduction for triage -> executor decision handoff."""

import json
from unittest.mock import patch
from lokay.organ.departments_boundary import handle_departments
from lokay.organ.issue_triage_department_boundary import handle_issue_triage_department
from lokay.organ.executor_department_boundary import handle_executor_department
from lokay.sieve_decision import decision_of


def test_triage_decisions_reach_executor_rows_in_factory_pass(tmp_path):
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()

    issues = [
        {"repo": "mikolaj92/msds-portal", "issue": 153, "labels": [], "title": "Park issue"},
        {"repo": "mikolaj92/msds-portal", "issue": 155, "labels": [], "title": "Skip issue"},
        {"repo": "mikolaj92/Docxtor", "issue": 161, "labels": [], "title": "Do issue"},
    ]
    listed = {"ok": True, "issues": issues, "count": len(issues), "overflow": False}

    # Simulate issue_triage_department output (what summarize_issue_triage_department returns)
    triage_decisions = [
        decision_of({"repo": "mikolaj92/msds-portal", "issue": 153, "route": "skip", "reason": "host_ops"}),
        decision_of({"repo": "mikolaj92/msds-portal", "issue": 155, "route": "skip", "reason": "host_ops"}),
        decision_of({"repo": "mikolaj92/Docxtor", "issue": 161, "route": "do", "reason": "ready"}),
    ]
    triage_dept_output = {
        "ok": True,
        "department": "issue_triage",
        "route": "cap",
        "result": {
            "decisions": triage_decisions,
            "leftover": 58,
            "department": "issue_triage",
        }
    }

    # Verify that run_executor_department passes triage decisions to run_executor_rows
    captured_triage = {}
    def fake_run_executor_rows(*args, **kwargs):
        captured_triage.update(kwargs.get("triage") or {})
        return {"ok": True, "route": "cap", "result": {}}

    up = {
        "factory_begin_host_gate": {"route": "begin"},
        "factory_begin": {"pass_dir": str(pass_dir)},
        "select_executor_department": {"route": "run"},
        "select_issue_triage_department": {"route": "run"},
        "run_issue_triage_department": triage_dept_output,
    }

    with patch("lokay.proc.run_executor_department.run", side_effect=fake_run_executor_rows):
        res = handle_departments("run_executor_department", {"config_path": None, "live": False}, up, {})

    assert res is not None
    assert captured_triage.get("decisions") == triage_decisions


def test_flat_fala_triage_payload_reaches_executor_rows(tmp_path):
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    triage_decisions = [
        decision_of({"repo": "mikolaj92/takt", "issue": 42, "route": "skip", "reason": "host_ops"}),
    ]
    flat = {
        "ok": True,
        "department": "issue_triage",
        "route": "cap",
        "decisions": triage_decisions,
        "leftover": 108,
        "leftover_issues": [{"repo": "mikolaj92/takt", "issue": 53}],
    }
    captured_triage = {}

    def fake_run_executor_rows(*args, **kwargs):
        captured_triage.update(kwargs.get("triage") or {})
        return {"ok": True, "route": "cap", "result": {}}

    up = {
        "factory_begin_host_gate": {"route": "begin"},
        "factory_begin": {"pass_dir": str(pass_dir)},
        "select_executor_department": {"route": "run"},
        "select_issue_triage_department": {"route": "run"},
        "run_issue_triage_department": flat,
    }
    with patch("lokay.proc.run_executor_department.run", side_effect=fake_run_executor_rows):
        handle_departments("run_executor_department", {"config_path": None, "live": False}, up, {})
    assert captured_triage.get("decisions") == triage_decisions
    assert captured_triage["leftover_issues"][0]["issue"] == 53
