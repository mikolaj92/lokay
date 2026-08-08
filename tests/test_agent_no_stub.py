"""Agent / LLM path: no stubs, no silent harness inventing; generic argv template."""

from pathlib import Path

import pytest

from lokay.agent import AgentError, build_agent_argv, build_grok_argv, resolve_agent_kind, run_agent
from lokay.config import Config, apply_env_overrides, load_config
from lokay.runner import Runner

OMP_ARGS = [
    "--cwd",
    "{cwd}",
    "-p",
    "{prompt}",
    "--auto-approve",
    "--model",
    "{model}",
    "--max-time",
    "{timeout}",
]
GROK_ARGS = [
    "--cwd",
    "{cwd}",
    "--always-approve",
    "--max-turns",
    "{max_turns}",
    "--output-format",
    "plain",
    "-m",
    "{model}",
    "--permission-mode",
    "bypassPermissions",
    "-p",
    "{prompt}",
]


def _clear_mill_env(monkeypatch):
    for key in (
        "LOKAY_MODE",
        "LOKAY_EXECUTOR_ENABLED",
        "LOKAY_AGENT",
        "LOKAY_MERGE_ENABLED",
        "LOKAY_REQUIRE_CHECKS",
        "LOKAY_OFFLINE",
        "LOKAY_CONFIG",
    ):
        monkeypatch.delenv(key, raising=False)


def test_template_omp_argv():
    cfg = Config(
        agent="omp",
        agent_command="omp",
        agent_model="omniroute/omp/default",
        agent_args=list(OMP_ARGS),
        timeout_seconds=1800,
    )
    argv = build_agent_argv(cfg, worktree=Path("/tmp/wt"), prompt="fix it")
    assert argv == [
        "omp",
        "--cwd",
        "/tmp/wt",
        "-p",
        "fix it",
        "--auto-approve",
        "--model",
        "omniroute/omp/default",
        "--max-time",
        "1800",
    ]


def test_template_grok_argv_via_same_builder():
    cfg = Config(
        agent="grok",
        agent_command="grok",
        agent_model="grok-4",
        agent_args=list(GROK_ARGS),
        max_turns=7,
    )
    argv = build_agent_argv(cfg, worktree=Path("/tmp/wt"), prompt="fix it")
    assert argv[0] == "grok"
    assert "-p" in argv and argv[argv.index("-p") + 1] == "fix it"
    assert argv[argv.index("-m") + 1] == "grok-4"
    assert "--permission-mode" in argv
    # alias still works
    assert build_grok_argv(cfg, worktree=Path("/tmp/wt"), prompt="fix it") == argv


def test_empty_model_drops_flag_pair():
    cfg = Config(
        agent="omp",
        agent_command="omp",
        agent_model=None,
        agent_args=list(OMP_ARGS),
    )
    argv = build_agent_argv(cfg, worktree=Path("/tmp/wt"), prompt="x")
    assert "--model" not in argv
    assert "{model}" not in argv


def test_empty_command_fails():
    cfg = Config(agent="omp", agent_command="", agent_args=list(OMP_ARGS))
    with pytest.raises(AgentError, match="command is empty"):
        build_agent_argv(cfg, worktree=Path("/tmp/wt"), prompt="x")


def test_empty_args_fails():
    cfg = Config(agent="omp", agent_command="omp", agent_args=[])
    with pytest.raises(AgentError, match="args is empty"):
        build_agent_argv(cfg, worktree=Path("/tmp/wt"), prompt="x")


def test_reject_fake(monkeypatch):
    monkeypatch.delenv("LOKAY_AGENT", raising=False)
    with pytest.raises(AgentError, match="forbidden"):
        resolve_agent_kind(Config(agent="fake", agent_command="omp", agent_args=list(OMP_ARGS)))
    monkeypatch.setenv("LOKAY_AGENT", "stub")
    with pytest.raises(AgentError, match="forbidden"):
        resolve_agent_kind(Config(agent="omp", agent_command="omp", agent_args=list(OMP_ARGS)))


def test_empty_agent_fails_closed(monkeypatch):
    monkeypatch.delenv("LOKAY_AGENT", raising=False)
    with pytest.raises(AgentError, match="not configured"):
        resolve_agent_kind(Config(agent="", agent_command="omp", agent_args=list(OMP_ARGS)))


def test_any_label_ok_if_not_stub(monkeypatch):
    monkeypatch.delenv("LOKAY_AGENT", raising=False)
    assert resolve_agent_kind(Config(agent="omp", agent_command="omp", agent_args=list(OMP_ARGS))) == "omp"
    assert resolve_agent_kind(Config(agent="grok", agent_command="grok", agent_args=list(GROK_ARGS))) == "grok"
    assert resolve_agent_kind(Config(agent="my-agent", agent_command="x", agent_args=["{prompt}"])) == "my-agent"


def test_planned_does_not_execute(tmp_path: Path):
    cfg = Config(agent="omp", agent_command="omp", agent_args=list(OMP_ARGS), executor_enabled=True)
    out = run_agent(Runner(), cfg, worktree=tmp_path, prompt="x", execute=False)
    assert out["status"] == "planned"
    assert out["agent"] == "omp"


def test_execute_true_with_executor_disabled_fails_closed(tmp_path: Path):
    cfg = Config(agent="omp", agent_command="omp", agent_args=list(OMP_ARGS), executor_enabled=False)
    with pytest.raises(AgentError, match="executor.enabled is false"):
        run_agent(Runner(), cfg, worktree=tmp_path, prompt="x", execute=True)


def test_load_config_empty_agent_fails(tmp_path: Path, monkeypatch):
    _clear_mill_env(monkeypatch)
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: dry-run
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  agent: ""
  command: omp
  args: ["-p", "{{prompt}}"]
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="agent"):
        load_config(cfg_path)


def test_load_config_empty_command_fails(tmp_path: Path, monkeypatch):
    _clear_mill_env(monkeypatch)
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: dry-run
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  agent: omp
  command: ""
  args: ["-p", "{{prompt}}"]
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="command"):
        load_config(cfg_path)
