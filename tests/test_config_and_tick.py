from pathlib import Path

from lokay.agent import build_agent_argv
from lokay.compose.tick import compose_tick
from lokay.config import Config, RepoConfig, load_config
from lokay.git_branch import branch_for_issue
from lokay.proc.make_branch import main as make_branch_main


def test_load_example(tmp_path: Path, monkeypatch):
    # File values only — do not inherit LaunchAgent mill env.
    for key in (
        "LOKAY_MODE",
        "LOKAY_EXECUTOR_ENABLED",
        "LOKAY_AGENT",
        "LOKAY_MERGE_ENABLED",
        "LOKAY_REQUIRE_CHECKS",
        "LOKAY_CONFIG",
    ):
        monkeypatch.delenv(key, raising=False)
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        """
mode: dry-run
github:
  assignee: mikolaj92
  ready_label: ai:ready
repos:
  - name: mikolaj92/lokay
    clone_path: {tmp_path}
    priority: 10
executor:
  enabled: false
  agent: grok
  command: grok
  max_turns: 12
""".replace("{tmp_path}", str(tmp_path)),
        encoding="utf-8",
    )
    cfg = load_config(cfg_path)
    assert cfg.mode == "dry-run"
    assert cfg.agent == "grok"
    assert cfg.validate() == []
    assert len(cfg.active_repos()) == 1


def test_env_overrides_enable_live_mill(tmp_path: Path, monkeypatch):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: dry-run
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: false
  agent: grok
merge:
  enabled: false
  require_checks: true
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("LOKAY_MODE", "live")
    monkeypatch.setenv("LOKAY_EXECUTOR_ENABLED", "1")
    monkeypatch.setenv("LOKAY_AGENT", "grok")
    monkeypatch.setenv("LOKAY_MERGE_ENABLED", "true")
    monkeypatch.setenv("LOKAY_REQUIRE_CHECKS", "0")
    cfg = load_config(cfg_path)
    assert cfg.mode == "live"
    assert cfg.executor_enabled is True
    assert cfg.agent == "grok"
    assert cfg.merge_enabled is True
    assert cfg.require_checks is False


def test_live_allows_missing_clone_in_validate(tmp_path: Path):
    """Scope lists repos even without local trees; implement needs clone later."""
    cfg = Config(
        mode="live",
        repos=[RepoConfig(name="a/b", clone_path=tmp_path / "missing")],
    )
    assert cfg.validate() == []
    assert len(cfg.active_repos()) == 1
    assert not cfg.active_repos()[0].clone_path.exists()


def test_agent_argv_from_template_not_vendor_branch():
    """Harness flags come from executor.args template — not hardcoded vendor switch."""
    grok_args = [
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
    cfg = Config(
        agent="grok",
        agent_command="grok",
        agent_model="grok-4",
        agent_args=list(grok_args),
        max_turns=7,
    )
    argv = build_agent_argv(cfg, worktree=Path("/tmp/wt"), prompt="fix it")
    assert argv[0] == "grok"
    assert "omp" not in argv
    assert "-p" in argv and argv[argv.index("-p") + 1] == "fix it"
    assert argv[argv.index("-m") + 1] == "grok-4"



def test_make_branch_atomic(capsys):
    code = make_branch_main(
        ["--prefix", "ai/fix", "--repo", "a/b", "--issue", "3", "--title", "Hello World"]
    )
    assert code == 0
    import json

    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["ok"] is True
    assert out["branch"].startswith("ai/fix/3-")
    assert branch_for_issue("ai/fix", "a/b", 3, "Hello World") == out["branch"]


def test_tick_offline_survey(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LOKAY_OFFLINE", "1")
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: dry-run
repos:
  - name: mikolaj92/lokay
    clone_path: {tmp_path}
executor:
  command: grok
  agent: grok
  enabled: false
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    result = compose_tick(config_path=str(cfg_path), live=False)
    assert result["ok"] is True
    assert result["live"] is False
    assert result["health"] == "offline"


def test_mill_offline_one_pass(tmp_path: Path, monkeypatch):
    from lokay.compose.mill import compose_mill

    monkeypatch.setenv("LOKAY_OFFLINE", "1")
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: dry-run
repos:
  - name: mikolaj92/lokay
    clone_path: {tmp_path}
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    result = compose_mill(config_path=str(cfg_path), live=False, max_passes=3)
    assert result.get("health") == "offline"
    assert result.get("passes") == 1


def test_tick_refuses_live_when_mode_dry(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: dry-run
repos:
  - name: mikolaj92/lokay
    clone_path: {tmp_path}
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    result = compose_tick(config_path=str(cfg_path), live=True)
    assert result["ok"] is False
