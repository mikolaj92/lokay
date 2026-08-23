from pathlib import Path

import pytest

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


def test_max_issue_to_pr_per_pass_default_and_legacy_alias(tmp_path: Path, monkeypatch):
    for key in ("LOKAY_MODE", "LOKAY_EXECUTOR_ENABLED", "LOKAY_AGENT", "LOKAY_CONFIG"):
        monkeypatch.delenv(key, raising=False)
    bare = tmp_path / "bare.yaml"
    bare.write_text(
        f"""
mode: dry-run
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: false
  command: true
  args: ["{{prompt}}"]
""",
        encoding="utf-8",
    )
    cfg = load_config(bare)
    assert cfg.max_issue_to_pr_per_pass == 1
    assert cfg.max_issues_per_tick == 1

    legacy = tmp_path / "legacy.yaml"
    legacy.write_text(
        bare.read_text() + """
limits:
  max_issues_per_tick: 2
""",
        encoding="utf-8",
    )
    cfg_legacy = load_config(legacy)
    assert cfg_legacy.max_issue_to_pr_per_pass == 2
    assert cfg_legacy.max_issues_per_tick == 2

    explicit = tmp_path / "explicit.yaml"
    explicit.write_text(
        bare.read_text() + """
limits:
  max_issue_to_pr_per_pass: 5
  max_issues_per_tick: 1
""",
        encoding="utf-8",
    )
    cfg_explicit = load_config(explicit)
    assert cfg_explicit.max_issue_to_pr_per_pass == 5
    assert cfg_explicit.max_issues_per_tick == 5


def test_quoted_yaml_false_does_not_enable_executor(tmp_path: Path, monkeypatch):
    """bool('false') is True in Python — quoted YAML must not arm the mill."""
    for key in ("LOKAY_MODE", "LOKAY_EXECUTOR_ENABLED", "LOKAY_AGENT", "LOKAY_CONFIG"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / "quoted.yaml"
    path.write_text(
        f"""
mode: dry-run
repos:
  - name: a/b
    clone_path: {tmp_path}
    enabled: "false"
executor:
  enabled: "false"
  agent: pi
  command: pi
  args: ["{{prompt}}"]
merge:
  enabled: "false"
  require_checks: "false"
  require_llm_review: "true"
""",
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.executor_enabled is False
    assert cfg.merge_enabled is False
    assert cfg.require_checks is False
    assert cfg.require_llm_review is True
    assert cfg.active_repos() == []


def test_committed_live_config_requires_llm_review(monkeypatch):
    """Quality gate: mill must not merge without a structured reviewer."""
    from pathlib import Path

    from lokay.config import load_config

    monkeypatch.delenv("LOKAY_REQUIRE_LLM_REVIEW", raising=False)
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    assert cfg.require_llm_review is True


def test_garbage_yaml_bool_fails_closed(tmp_path: Path, monkeypatch):
    for key in ("LOKAY_MODE", "LOKAY_EXECUTOR_ENABLED", "LOKAY_AGENT", "LOKAY_CONFIG"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / "bad.yaml"
    path.write_text(
        f"""
mode: dry-run
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: maybe
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="executor.enabled"):
        load_config(path)


def test_unused_self_repair_and_approve_knobs_are_gone():
    assert "always_approve" not in Config.__dataclass_fields__
    assert "max_self_repair_attempts" not in Config.__dataclass_fields__


def test_dead_require_test_evidence_knob_is_gone():
    """String matcher was never a merge gate. YAML must not pretend it is."""
    from pathlib import Path

    from lokay import safety

    root = Path(__file__).resolve().parents[1]
    yaml = (root / "config.yaml").read_text(encoding="utf-8")
    assert "require_test_evidence" not in yaml
    assert "require_test_evidence" not in Config.__dataclass_fields__
    assert not hasattr(safety, "looks_like_test_evidence")


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
  command: grok
  args: ["{{prompt}}"]
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
    args = [
        "-p",
        "{prompt}",
        "--model",
        "{model}",
        "--approve",
        "--no-session",
    ]
    cfg = Config(
        agent="pi",
        agent_command="pi",
        agent_model="omniroute/pi",
        agent_args=list(args),
        timeout_seconds=99,
    )
    argv = build_agent_argv(cfg, worktree=Path("/tmp/wt"), prompt="fix it")
    assert argv == [
        "pi",
        "-p",
        "fix it",
        "--model",
        "omniroute/pi",
        "--approve",
        "--no-session",
    ]
    assert "--cwd" not in argv


def test_make_branch_atomic(capsys):
    code = make_branch_main(
        [
            "--prefix",
            "ai/fix",
            "--repo",
            "mikolaj92/lokay",
            "--issue",
            "3",
            "--title",
            "Hello World",
        ]
    )
    assert code == 0
    import json

    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["ok"] is True
    assert out["branch"].startswith("ai/fix/3-")
    assert (
        branch_for_issue("ai/fix", "mikolaj92/lokay", 3, "Hello World") == out["branch"]
    )


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


def test_tick_routes_request_changes_to_repair_and_keeps_pr_open(tmp_path, monkeypatch):
    from lokay.compose import tick

    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: live
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: true
  command: omp
  args: ["-p", "{{prompt}}"]
merge:
  enabled: true
  require_checks: false
  require_llm_review: true
limits:
  max_triage_per_tick: 0
  max_issues_per_tick: 0
  max_repairs_per_tick: 1
worktrees:
  root: {tmp_path / 'wt'}
state:
  path: {tmp_path / 'state.jsonl'}
""",
        encoding="utf-8",
    )
    branch = "ai/fix/7-x"

    def fake_run(fn, argv):
        if fn is tick.p_list_prs.main:
            return {
                "ok": True,
                "prs": [{"number": 12, "head_ref": branch, "mergeable": "MERGEABLE"}],
            }
        if fn in {tick.p_list_inbox.main, tick.p_list_issues.main}:
            key = "issues"
            return {"ok": True, key: []}
        if fn is tick.p_checks.main:
            return {"ok": True, "status": "none", "merge_ok": True}
        raise AssertionError(f"unexpected atom: {fn}")

    triage_calls = []
    repair_calls = []

    def fake_triage(**kwargs):
        triage_calls.append(kwargs)
        return {
            "ok": True,
            "skipped": True,
            "reason": "llm_review_requested_changes",
            "repairable": True,
            "review": {
                "verdict": "request_changes",
                "secrets": False,
                "blocking": ["validate theme"],
            },
        }

    def fake_repair(**kwargs):
        repair_calls.append(kwargs)
        return {"ok": True, "pushed": True}

    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(tick, "compose_pr_triage", fake_triage)
    monkeypatch.setattr(tick, "compose_pr_repair", fake_repair)
    result = tick.compose_tick(config_path=str(cfg_path), live=True)

    assert len(triage_calls) == 1
    assert len(repair_calls) == 1
    assert repair_calls[0]["review"]["blocking"] == ["validate theme"]
    # Running/pushing a repair is an attempt, not proven queue movement.  The PR
    # stays open; health is repairing (honest wait), not mill-failing stall.
    assert result["progress"] == 0
    assert result["health"] == "repairing"
    assert result["ok"] is True
    assert result["remaining"]["needs_repair"] == 1
    assert result["remaining"]["open_ai_prs"] == 1
    assert any(action["step"] == "pr_review_repair" for action in result["actions"])


def test_agent_executor_environment_strips_health_lease(tmp_path):
    from lokay.agent import run_agent
    from lokay.runner import CommandResult

    class CapturingRunner:
        spec = None

        def run(self, spec, *, live):
            self.spec = spec
            return CommandResult(spec=spec, executed=True, returncode=0)

    cfg = Config(
        mode="live",
        executor_enabled=True,
        agent="omp",
        agent_command="true",
        agent_args=["{{prompt}}"],
    )
    runner = CapturingRunner()
    run_agent(runner, cfg, worktree=tmp_path, prompt="x", execute=True)
    assert runner.spec.env["LOKAY_HEALTH_LEASE"] == ""
