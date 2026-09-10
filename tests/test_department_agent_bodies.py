"""Department bodies: high-entropy agent slots with authored child fallback."""

from __future__ import annotations

from pathlib import Path

import pytest

from lokay.agent import build_agent_argv, session_id_for_worktree
from lokay.capabilities import executor_environment
from lokay.config import Config, department_enabled, load_config
from lokay.proc.department_agent_runtime import (
    DEPARTMENTS,
    execute_department_agent,
    normalize,
    prompt_for,
)
from lokay.proc.run_executor_department import run as run_executor
from lokay.proc.run_issue_triage_department import run as run_issue_triage
from lokay.proc.run_pr_repair_department import run as run_pr_repair
from lokay.proc.run_pr_triage_department import run as run_pr_triage
from lokay.proc.run_self_repair_department import run as run_self_repair


def _cfg(**extra: object) -> Config:
    values = dict(
        mode="live",
        executor_enabled=True,
        agent="pi",
        agent_command="pi",
        agent_args=["-p", "{prompt}", "--session-id", "{session}"],
        department_agent_bodies=True,
    )
    values.update(extra)
    return Config(**values)


def test_five_department_contracts_exist():
    for name in DEPARTMENTS:
        text = prompt_for(name, pass_dir="/pass")
        assert "Return ONLY one JSON object" in text
        assert "trace" in text
        assert "Fala geometry" in text


def test_issue_triage_normalizes_launched_null():
    out = normalize(
        "issue_triage",
        {
            "ok": True,
            "department": "issue_triage",
            "route": "do",
            "launched": "started",
            "trace": "listed issues then marked do",
            "result": {"launched": "started"},
        },
    )
    assert out is not None
    assert out["launched"] is None
    assert out["result"]["launched"] is None
    assert out["body"] == "agent"


def test_executor_normalizes_merged_false():
    out = normalize(
        "executor",
        {
            "ok": True,
            "department": "executor",
            "route": "started",
            "merged": True,
            "trace": "detached issue_to_pr",
        },
    )
    assert out is not None
    assert out["merged"] is False
    assert out["result"]["merged"] is False


def test_pr_triage_normalizes_repair_not_started():
    out = normalize(
        "pr_triage",
        {
            "ok": True,
            "department": "pr_triage",
            "route": "completed",
            "verdict": "repair",
            "repair_started": True,
            "trace": "checks red, verdict repair",
        },
    )
    assert out is not None
    assert out["repair_started"] is False
    assert out["result"]["repair_started"] is False
    assert out["verdict"] == "repair"


def test_missing_trace_is_not_a_body():
    assert (
        normalize(
            "self_repair",
            {"ok": True, "department": "self_repair", "route": "skip"},
        )
        is None
    )


def test_route_child_is_not_a_body():
    assert (
        normalize(
            "issue_triage",
            {
                "ok": True,
                "department": "issue_triage",
                "route": "child",
                "launched": None,
                "trace": "cannot list issues",
            },
        )
        is None
    )


def test_wrong_department_is_not_a_body():
    assert (
        normalize(
            "executor",
            {
                "ok": True,
                "department": "issue_triage",
                "route": "idle",
                "merged": False,
                "trace": "no",
            },
        )
        is None
    )


class _FakeRunner:
    def __init__(self, stdout: str, returncode: int = 0, timed_out: bool = False):
        self.stdout = stdout
        self.returncode = returncode
        self.timed_out = timed_out
        self.specs = []

    def run(self, spec, *, live: bool):
        self.specs.append(spec)
        return type(
            "Result",
            (),
            {
                "returncode": self.returncode,
                "stdout": self.stdout,
                "stderr": "",
                "timed_out": self.timed_out,
            },
        )()


def test_valid_agent_json_is_the_body(monkeypatch, tmp_path: Path):
    runner = _FakeRunner(
        '{"ok":true,"department":"issue_triage","route":"idle","launched":null,'
        '"trace":"listed zero issues"}'
    )
    monkeypatch.setattr(
        "lokay.proc.department_agent_runtime.runner", lambda _cfg=None: runner
    )
    monkeypatch.setattr(
        "lokay.proc.department_agent_runtime.agent_execute_allowed",
        lambda *_a, **_k: True,
    )
    child_calls = {"n": 0}

    def child() -> dict:
        child_calls["n"] += 1
        raise AssertionError("authored child must not run when the agent envelope is valid")

    out = execute_department_agent(
        "issue_triage",
        cfg=_cfg(),
        live=True,
        prompt="x",
        child=child,
        pass_dir=str(tmp_path),
    )
    assert child_calls["n"] == 0
    assert out["body"] == "agent"
    assert out["route"] == "idle"
    assert out["launched"] is None
    assert "listed zero issues" in out["trace"]
    assert runner.specs[0].env["LOKAY_CAPABILITIES"]
    assert "github.read" in runner.specs[0].env["LOKAY_CAPABILITIES"]


def test_invalid_json_falls_back_to_child(monkeypatch, tmp_path: Path):
    runner = _FakeRunner("not json")
    monkeypatch.setattr(
        "lokay.proc.department_agent_runtime.runner", lambda _cfg=None: runner
    )
    monkeypatch.setattr(
        "lokay.proc.department_agent_runtime.agent_execute_allowed",
        lambda *_a, **_k: True,
    )
    out = execute_department_agent(
        "issue_triage",
        cfg=_cfg(),
        live=True,
        prompt="x",
        child=lambda: {"ok": True, "route": "idle", "department": "issue_triage"},
        pass_dir=str(tmp_path),
    )
    assert out["body"] == "child"
    assert out["agent_status"] == "invalid_json"
    assert out["route"] == "idle"


def test_timeout_falls_back_to_child(monkeypatch, tmp_path: Path):
    runner = _FakeRunner("", timed_out=True, returncode=124)
    monkeypatch.setattr(
        "lokay.proc.department_agent_runtime.runner", lambda _cfg=None: runner
    )
    monkeypatch.setattr(
        "lokay.proc.department_agent_runtime.agent_execute_allowed",
        lambda *_a, **_k: True,
    )
    out = execute_department_agent(
        "executor",
        cfg=_cfg(),
        live=True,
        prompt="x",
        child=lambda: {"ok": True, "route": "idle", "merged": False},
        pass_dir=str(tmp_path),
    )
    assert out["body"] == "child"
    assert out["agent_timed_out"] is True


def test_disabled_agent_bodies_call_child(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.run_issue_triage_department.run_path",
        lambda **kwargs: {"ok": True, "path": kwargs["path_id"]},
    )
    out = run_issue_triage(pass_dir="/pass", config_path=None, live=False)
    assert out["body"] == "child"
    assert out["path"] == "issue_triage_department"


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


def test_department_session_is_not_coding_session(tmp_path: Path):
    code = session_id_for_worktree(tmp_path)
    dept = session_id_for_worktree(tmp_path, kind="department-issue-triage")
    assert dept != code
    assert dept.endswith("-department-issue-triage")
    argv = build_agent_argv(
        _cfg(),
        worktree=tmp_path,
        prompt="judge",
        session_kind="department-issue-triage",
    )
    assert argv[-1] == dept


def test_department_role_keeps_github_credentials():
    env = executor_environment(
        "department",
        {
            "GH_TOKEN": "secret",
            "GITHUB_TOKEN": "also",
            "PATH": "/bin",
            "HOME": "/tmp/home",
        },
    )
    assert env["GH_TOKEN"] == "secret"
    assert env["GITHUB_TOKEN"] == "also"
    assert "github.write" in env["LOKAY_CAPABILITIES"]
    assert "pr.merge" in env["LOKAY_CAPABILITIES"]


def test_config_agent_bodies_switch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("LOKAY_DEPARTMENT_AGENT_BODIES", raising=False)
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        "mode: dry-run\ndepartments:\n  agent_bodies: false\nrepos: []\n",
        encoding="utf-8",
    )
    cfg = load_config(cfg_path)
    assert cfg.department_agent_bodies is False
    assert department_enabled(cfg, "issue_triage") is True
