from pathlib import Path

import pytest

from lokay.agent import AgentError, build_grok_argv, resolve_agent_kind, run_agent
from lokay.config import Config
from lokay.runner import Runner


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


def test_reject_fake(monkeypatch):
    monkeypatch.delenv("LOKAY_AGENT", raising=False)
    cfg = Config(agent="fake")
    with pytest.raises(AgentError, match="forbidden"):
        resolve_agent_kind(cfg)
    monkeypatch.setenv("LOKAY_AGENT", "stub")
    with pytest.raises(AgentError, match="forbidden"):
        resolve_agent_kind(Config(agent="grok"))


def test_planned_does_not_execute(tmp_path: Path):
    cfg = Config(agent="grok", executor_enabled=True)
    out = run_agent(Runner(), cfg, worktree=tmp_path, prompt="x", execute=False)
    assert out["status"] == "planned"
    assert out["agent"] == "grok"
