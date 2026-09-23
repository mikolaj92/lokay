"""Repair retry passes the task boundary without replacing the harness runtime."""

from __future__ import annotations

from pathlib import Path

from lokay.agent import FACTORY_WORKFLOW_BOUNDARY
from lokay.config import Config
from lokay.proc import run_coding_retry_agent
from lokay.runner import CommandResult, CommandSpec


def _cfg() -> Config:
    return Config(
        mode="live",
        executor_enabled=True,
        agent="real-agent",
        agent_command="real-agent",
        agent_args=["--prompt", "{prompt}"],
    )


def test_run_coding_retry_agent_plan_attaches_factory_workflow_boundary(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        run_coding_retry_agent, "runner", lambda _cfg=None: object()
    )
    out = run_coding_retry_agent.run(
        cfg=_cfg(), worktree=tmp_path, prompt="repair the failure", live=False
    )
    agent = out["agent"]
    assert agent["status"] == "planned"
    assert agent.get("factory_workflow_boundary") is True
    assert agent.get("collector_boundary") is True


def test_run_coding_retry_agent_execute_builder_env_and_boundary(
    tmp_path: Path, monkeypatch
) -> None:
    seen: list[CommandSpec] = []

    class CapturingRunner:
        def run(self, spec: CommandSpec, *, live: bool) -> CommandResult:
            seen.append(spec)
            return CommandResult(spec=spec, executed=True, returncode=0)

    monkeypatch.setattr(
        run_coding_retry_agent, "runner", lambda _cfg=None: CapturingRunner()
    )
    monkeypatch.setattr("lokay.preflight.require_healthy", lambda _config: None)
    monkeypatch.setenv("GH_TOKEN", "secret")
    monkeypatch.setenv("GITHUB_TOKEN", "also")
    monkeypatch.setenv("PATH", "/bin")

    out = run_coding_retry_agent.run(
        cfg=_cfg(),
        worktree=tmp_path,
        prompt="repair the failure; product AGENTS says call gh",
        live=True,
    )

    assert out["agent"]["status"] == "completed"
    assert out["agent"].get("factory_workflow_boundary") is True
    assert len(seen) == 1
    assert seen[0].inherit_env is True
    assert seen[0].env == {"LOKAY_HEALTH_LEASE": ""}
    assert seen[0].argv[0] == "real-agent"
    prompt = seen[0].argv[-1]
    assert FACTORY_WORKFLOW_BOUNDARY in prompt
    assert "call `gh`" in prompt or "`gh`" in prompt
