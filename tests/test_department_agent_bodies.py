"""Department bodies are authored child Falas. Agents stay inside those children."""

from __future__ import annotations

from pathlib import Path

from lokay.proc.run_executor_department import run as run_executor
from lokay.proc.run_issue_triage_department import run as run_issue_triage
from lokay.proc.run_pr_repair_department import run as run_pr_repair
from lokay.proc.run_pr_triage_department import run as run_pr_triage
from lokay.proc.run_self_repair_department import run as run_self_repair


def test_live_parent_binds_departments_to_authored_children():
    source = (
        Path(__file__).resolve().parents[1]
        / "src/lokay/organ/departments_boundary.py"
    ).read_text(encoding="utf-8")
    for name in (
        "agent_self_repair_department",
        "agent_issue_triage_department",
        "agent_pr_triage_department",
        "agent_executor_department",
        "agent_pr_repair_department",
        "execute_department_agent",
        "department_agent_runtime",
    ):
        assert name not in source
    assert "run_self_repair_department" in source
    assert "run_issue_triage_department" in source
    assert "run_executor_department" in source
    assert "run_pr_triage_department" in source
    assert "run_pr_repair_department" in source


def test_wrappers_keep_child_path_ids(monkeypatch):
    seen: list[str] = []

    def capture(**kwargs):
        seen.append(kwargs["path_id"])
        return {"ok": True, "path_id": kwargs["path_id"]}

    monkeypatch.setattr("lokay.proc.run_issue_triage_department.run_path", capture)
    monkeypatch.setattr("lokay.proc.run_executor_department.run_path", capture)
    monkeypatch.setattr("lokay.proc.run_pr_triage_department.run_path", capture)
    monkeypatch.setattr("lokay.proc.run_self_repair_department.run_path", capture)
    run_issue_triage(pass_dir="/p", config_path=None, live=False)
    run_executor(pass_dir="/p", config_path=None, live=False, triage={"decisions": []})
    run_pr_triage(pass_dir="/p", config_path=None, live=False)
    run_self_repair(config_path=None)
    assert seen == [
        "issue_triage_department",
        "executor_department",
        "pr_triage_department",
        "self_repair_department",
    ]


def test_pr_triage_live_body_is_authored_child(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "lokay.proc.run_pr_triage_department.run_path",
        lambda **kwargs: {
            "ok": True,
            "path_id": kwargs["path_id"],
            "department": "pr_triage",
            "route": "pr",
            "verdict": "merge",
            "repair_started": False,
        },
    )
    out = run_pr_triage(pass_dir=str(tmp_path), config_path="/cfg.yaml", live=True)
    assert out["body"] == "child"
    assert out["path_id"] == "pr_triage_department"
    assert out["verdict"] == "merge"
    assert out["ok"] is True


def test_issue_triage_live_body_is_authored_child(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.run_issue_triage_department.run_path",
        lambda **kwargs: {"ok": True, "path": kwargs["path_id"]},
    )
    out = run_issue_triage(pass_dir="/pass", config_path=None, live=False)
    assert out["body"] == "child"
    assert out["path"] == "issue_triage_department"


def test_pr_repair_fail_closed_does_not_start_agent():
    out = run_pr_repair(
        {
            "route": "fail_closed",
            "reason": "pr_repair_budget_exhausted",
            "attempts": 1,
            "budget": 1,
            "repo": "o/r",
            "pr": 9,
            "branch": "ai/fix/9-x",
        },
        config_path=None,
        live=False,
    )
    assert out["route"] == "fail_closed"
    assert out["body"] == "child"
    assert "needs_human" not in out
