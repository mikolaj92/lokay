from pathlib import Path

from lokay.agent import build_grok_argv, run_fake_agent
from lokay.compose.tick import compose_tick
from lokay.config import Config, RepoConfig, load_config
from lokay.git_branch import branch_for_issue
from lokay.proc.make_branch import main as make_branch_main


def test_load_example(tmp_path: Path):
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
  agent: fake
  command: grok
  max_turns: 12
""".replace("{tmp_path}", str(tmp_path)),
        encoding="utf-8",
    )
    cfg = load_config(cfg_path)
    assert cfg.mode == "dry-run"
    assert cfg.agent == "fake"
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
    monkeypatch.setenv("LOKAY_AGENT", "fake")
    monkeypatch.setenv("LOKAY_MERGE_ENABLED", "true")
    monkeypatch.setenv("LOKAY_REQUIRE_CHECKS", "0")
    cfg = load_config(cfg_path)
    assert cfg.mode == "live"
    assert cfg.executor_enabled is True
    assert cfg.agent == "fake"
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


def test_grok_argv_uses_grok_not_omp():
    cfg = Config(grok_command="grok", max_turns=7, always_approve=True, grok_model="grok-4")
    argv = build_grok_argv(cfg, worktree=Path("/tmp/wt"), prompt="fix it")
    assert argv[0] == "grok"
    assert "omp" not in argv


def test_fake_agent_writes_marker(tmp_path: Path):
    (tmp_path / "CANARY_TODO.txt").write_text("FIXME please\n", encoding="utf-8")
    result = run_fake_agent(worktree=tmp_path, prompt="fix canary")
    assert result["status"] == "completed"
    assert (tmp_path / "LOKAY_CANARY.md").is_file()
    assert "fixed" in (tmp_path / "CANARY_TODO.txt").read_text(encoding="utf-8")


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
  agent: fake
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
