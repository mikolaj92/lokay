"""Zero budget admits nothing. Dry-run does not become a live child."""

from lokay.organ.implementation_dispatch_boundary import handle_implementation_dispatch
from lokay.organ.issues_boundary import handle_issues
from lokay.organ.triage_dispatch_boundary import handle_triage_dispatch
from lokay.proc.select_executor_slot import select as select_executor
from lokay.proc.select_issue_sieve_slot import select as select_sieve


def test_zero_budget_skips_the_first_executor_slot():
    prepared = {"ok": True, "budget": 0, "spent": 0, "slot_count": 8}
    assert select_executor(prepared, {}, slot=1)["route"] == "empty"


def test_zero_budget_skips_the_first_sieve_slot():
    prepared = {"ok": True, "budget": 0, "spent": 0, "slot_count": 5}
    assert select_sieve(prepared, {}, slot=1)["route"] == "empty"


def test_positive_budget_still_admits_the_first_slot():
    prepared = {"ok": True, "budget": 1, "spent": 0, "slot_count": 8}
    assert select_executor(prepared, {}, slot=1)["route"] == "run"
    assert select_sieve(prepared, {}, slot=1)["route"] == "run"


def test_spent_budget_still_skips():
    prepared = {"ok": True, "budget": 0, "spent": 1, "slot_count": 8}
    assert select_executor(prepared, {}, slot=1)["route"] == "empty"


def test_dry_run_launch_does_not_detach(monkeypatch):
    def boom(**_k):
        raise AssertionError("dry-run launched a worker")

    monkeypatch.setattr("lokay.proc.launch_issue_to_pr.detach_issue_to_pr", boom)
    out = handle_issues(
        "issues_launch_pr",
        {"live": False, "config_path": ""},
        {"select_issue_executor": {"route": "do", "repo": "o/r", "issue": 1}},
        {},
    )
    assert out is not None
    assert out["route"] == "skipped"
    assert out["reason"] == "dry_run"


def test_dry_run_dispatch_launch_does_not_detach(monkeypatch):
    def boom(**_k):
        raise AssertionError("dry-run launched a worker")

    monkeypatch.setattr("lokay.proc.launch_issue_to_pr.detach_issue_to_pr", boom)
    out = handle_implementation_dispatch(
        "launch_issue_to_pr",
        {"live": False, "config_path": "", "pass_dir": ""},
        {"select_ready_outcome": {"route": "do", "repo": "o/r", "issue": 1}},
        {},
    )
    assert out is not None
    assert out["route"] == "skipped"
    assert out["reason"] == "dry_run"


def test_dry_run_triage_does_not_run_live(monkeypatch):
    def boom(**_k):
        raise AssertionError("dry-run triage ran live")

    monkeypatch.setattr("lokay.proc.run_issue_triage_subflow.run_path", boom)
    out = handle_issues(
        "issues_run_triage",
        {"live": False, "config_path": ""},
        {"select_next_issue": {"route": "issue", "repo": "o/r", "issue": 7}},
        {},
    )
    assert out is not None
    assert out["route"] == "skipped"
    assert out["reason"] == "dry_run"


def test_dry_run_triage_dispatch_does_not_run_live(monkeypatch):
    def boom(**_k):
        raise AssertionError("dry-run triage ran live")

    monkeypatch.setattr("lokay.proc.run_issue_triage_subflow.run_path", boom)
    out = handle_triage_dispatch(
        "run_issue_triage_subflow",
        {"live": False, "config_path": "", "pass_dir": ""},
        {"select_triage_gate": {"route": "issue", "repo": "o/r", "issue": 7}},
        {},
    )
    assert out is not None
    assert out["route"] == "skipped"
    assert out["reason"] == "dry_run"
