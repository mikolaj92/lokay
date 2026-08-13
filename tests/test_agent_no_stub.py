"""Agent path: one harness slot; no stubs; no vendor hardcoding."""

from pathlib import Path

import pytest

from lokay.agent import AgentError, build_agent_argv, resolve_agent_kind, run_agent
from lokay.config import Config, load_config
from lokay.runner import Runner

# Default Pi invocation uses the configured OmniRoute combo.
PI_ARGS = [
    "-p",
    "{prompt}",
    "--model",
    "{model}",
    "--approve",
    "--no-session",
]
# Optional harness that wants an explicit model via template.
ALT_ARGS = [
    "--cwd",
    "{cwd}",
    "-p",
    "{prompt}",
    "--model",
    "{model}",
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


def test_pi_argv_with_model():
    cfg = Config(
        agent="pi",
        agent_command="pi",
        agent_model="omniroute/pi",
        agent_args=list(PI_ARGS),
        timeout_seconds=1800,
    )
    argv = build_agent_argv(cfg, worktree=Path("/tmp/wt"), prompt="implement issue")
    assert argv == [
        "pi",
        "-p",
        "implement issue",
        "--model",
        "omniroute/pi",
        "--approve",
        "--no-session",
    ]


def test_optional_model_in_template_when_set():
    cfg = Config(
        agent="alt",
        agent_command="alt-agent",
        agent_model="some-model",
        agent_args=list(ALT_ARGS),
    )
    argv = build_agent_argv(cfg, worktree=Path("/tmp/wt"), prompt="x")
    assert argv[argv.index("--model") + 1] == "some-model"


def test_empty_model_drops_flag_pair():
    cfg = Config(
        agent="alt",
        agent_command="alt-agent",
        agent_model=None,
        agent_args=list(ALT_ARGS),
    )
    argv = build_agent_argv(cfg, worktree=Path("/tmp/wt"), prompt="x")
    assert "--model" not in argv
    assert "{model}" not in argv


def test_empty_command_fails():
    cfg = Config(agent="pi", agent_command="", agent_args=list(PI_ARGS))
    with pytest.raises(AgentError, match="command is empty"):
        build_agent_argv(cfg, worktree=Path("/tmp/wt"), prompt="x")


def test_empty_args_fails():
    cfg = Config(agent="pi", agent_command="pi", agent_args=[])
    with pytest.raises(AgentError, match="args is empty"):
        build_agent_argv(cfg, worktree=Path("/tmp/wt"), prompt="x")


def test_reject_fake(monkeypatch):
    monkeypatch.delenv("LOKAY_AGENT", raising=False)
    with pytest.raises(AgentError, match="forbidden"):
        resolve_agent_kind(Config(agent="fake", agent_command="pi", agent_args=list(PI_ARGS)))


def test_empty_agent_fails_closed(monkeypatch):
    monkeypatch.delenv("LOKAY_AGENT", raising=False)
    with pytest.raises(AgentError, match="not configured"):
        resolve_agent_kind(Config(agent="", agent_command="pi", agent_args=list(PI_ARGS)))


def test_any_label_ok_if_not_stub(monkeypatch):
    monkeypatch.delenv("LOKAY_AGENT", raising=False)
    assert resolve_agent_kind(Config(agent="pi", agent_command="pi", agent_args=list(PI_ARGS))) == "pi"
    assert resolve_agent_kind(Config(agent="my-agent", agent_command="x", agent_args=["{prompt}"])) == "my-agent"


def test_planned_does_not_execute(tmp_path: Path):
    cfg = Config(agent="pi", agent_command="pi", agent_args=list(PI_ARGS), executor_enabled=True)
    out = run_agent(Runner(), cfg, worktree=tmp_path, prompt="x", execute=False)
    assert out["status"] == "planned"
    assert out["agent"] == "pi"


def test_execute_true_with_executor_disabled_fails_closed(tmp_path: Path):
    cfg = Config(agent="pi", agent_command="pi", agent_args=list(PI_ARGS), executor_enabled=False)
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
  enabled: true
  agent: ""
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
  enabled: true
  agent: pi
  command: ""
  args: ["-p", "{{prompt}}"]
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="command"):
        load_config(cfg_path)


def test_enabled_executor_omitted_args_fails_closed(tmp_path: Path, monkeypatch):
    """No silent Pi argv when executor.enabled and args are omitted."""
    _clear_mill_env(monkeypatch)
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: dry-run
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: true
  agent: pi
  command: pi
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="args"):
        load_config(cfg_path)


def test_enabled_executor_omitted_command_fails_closed(tmp_path: Path, monkeypatch):
    _clear_mill_env(monkeypatch)
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: dry-run
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: true
  agent: pi
  args: ["-p", "{{prompt}}"]
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="command"):
        load_config(cfg_path)
