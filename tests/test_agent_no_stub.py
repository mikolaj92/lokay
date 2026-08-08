"""Agent / LLM path: no stubs, no silent harness/model inventing (issue #18)."""

from pathlib import Path

import pytest

from lokay.agent import AgentError, build_grok_argv, resolve_agent_kind, run_agent
from lokay.config import Config, apply_env_overrides, load_config
from lokay.runner import Runner


def _clear_mill_env(monkeypatch):
    """Isolate tests from LaunchAgent / factory env overrides."""
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


def test_grok_argv():
    cfg = Config(grok_command="grok", max_turns=7, always_approve=True, grok_model="grok-4")
    argv = build_grok_argv(cfg, worktree=Path("/tmp/wt"), prompt="fix it")
    assert argv[0] == "grok"
    assert "omp" not in argv
    # Headless: -p/--single, not bare positional (TUI needs a TTY).
    assert "-p" in argv
    assert argv[argv.index("-p") + 1] == "fix it"
    assert argv[-1] == "fix it"
    assert "--output-format" in argv
    assert "--always-approve" in argv
    assert "--max-turns" in argv
    assert "--permission-mode" in argv
    assert argv[argv.index("--permission-mode") + 1] == "bypassPermissions"
    assert "-m" in argv
    assert argv[argv.index("-m") + 1] == "grok-4"


def test_grok_argv_omits_model_when_unset_no_invented_model():
    """Missing model must not invent a substitute model name."""
    cfg = Config(grok_command="grok", grok_model=None)
    argv = build_grok_argv(cfg, worktree=Path("/tmp/wt"), prompt="x")
    assert "-m" not in argv


def test_grok_argv_empty_command_fails_closed():
    cfg = Config(grok_command="")
    with pytest.raises(AgentError, match="command is empty"):
        build_grok_argv(cfg, worktree=Path("/tmp/wt"), prompt="x")


def test_reject_fake(monkeypatch):
    monkeypatch.delenv("LOKAY_AGENT", raising=False)
    cfg = Config(agent="fake")
    with pytest.raises(AgentError, match="forbidden"):
        resolve_agent_kind(cfg)
    monkeypatch.setenv("LOKAY_AGENT", "stub")
    with pytest.raises(AgentError, match="forbidden"):
        resolve_agent_kind(Config(agent="grok"))


def test_empty_agent_fails_closed_no_silent_grok(monkeypatch):
    """Empty agent must not invent harness name via ``or "grok"``."""
    monkeypatch.delenv("LOKAY_AGENT", raising=False)
    with pytest.raises(AgentError, match="not configured"):
        resolve_agent_kind(Config(agent=""))
    with pytest.raises(AgentError, match="not configured"):
        resolve_agent_kind(Config(agent="   "))


def test_whitespace_env_agent_does_not_override_config(monkeypatch):
    monkeypatch.setenv("LOKAY_AGENT", "  ")
    assert resolve_agent_kind(Config(agent="grok")) == "grok"


def test_planned_does_not_execute(tmp_path: Path):
    cfg = Config(agent="grok", executor_enabled=True)
    out = run_agent(Runner(), cfg, worktree=tmp_path, prompt="x", execute=False)
    assert out["status"] == "planned"
    assert out["agent"] == "grok"


def test_execute_true_with_executor_disabled_fails_closed(tmp_path: Path):
    """execute=True must not silently downgrade to planned when executor off."""
    cfg = Config(agent="grok", executor_enabled=False)
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
  command: grok
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
  agent: grok
  command: ""
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="command"):
        load_config(cfg_path)


def test_apply_env_rejects_empty_agent_after_override(monkeypatch):
    cfg = Config(agent="grok")
    cfg.agent = ""
    monkeypatch.delenv("LOKAY_AGENT", raising=False)
    with pytest.raises(ValueError, match="empty"):
        apply_env_overrides(cfg)


def test_run_agent_cli_live_refuses_when_executor_off(tmp_path: Path, capsys, monkeypatch):
    """--live + executor disabled is error, not ok/planned synthetic success."""
    import json

    from lokay.proc.run_agent import main as run_agent_main

    _clear_mill_env(monkeypatch)
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: live
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: false
  agent: grok
  command: grok
""",
        encoding="utf-8",
    )
    code = run_agent_main(
        [
            "--config",
            str(cfg_path),
            "--live",
            "--worktree",
            str(tmp_path),
            "--prompt",
            "do work",
        ]
    )
    assert code != 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["ok"] is False
    assert payload.get("status") == "refused"
    assert "executor.enabled" in str(payload.get("error", ""))


def test_run_agent_cli_live_refuses_when_mode_dry(tmp_path: Path, capsys, monkeypatch):
    import json

    from lokay.proc.run_agent import main as run_agent_main

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
  agent: grok
  command: grok
""",
        encoding="utf-8",
    )
    code = run_agent_main(
        [
            "--config",
            str(cfg_path),
            "--live",
            "--worktree",
            str(tmp_path),
            "--prompt",
            "do work",
        ]
    )
    assert code != 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["ok"] is False
    assert payload.get("status") == "refused"


def test_run_agent_cli_plan_without_live_still_ok(tmp_path: Path, capsys, monkeypatch):
    import json

    from lokay.proc.run_agent import main as run_agent_main

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
  agent: grok
  command: grok
""",
        encoding="utf-8",
    )
    code = run_agent_main(
        [
            "--config",
            str(cfg_path),
            "--worktree",
            str(tmp_path),
            "--prompt",
            "plan only",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["ok"] is True
    assert payload["status"] == "planned"


def test_validate_flags_empty_agent_command():
    cfg = Config(agent="", grok_command="")
    errs = cfg.validate()
    assert any("agent" in e for e in errs)
    assert any("command" in e for e in errs)
