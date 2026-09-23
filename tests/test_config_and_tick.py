from pathlib import Path

import pytest

from lokay.agent import build_agent_argv
from lokay.config import Config, RepoConfig, load_config
from lokay.git_branch import branch_for_issue
from lokay.passkit import io as pass_io
from lokay.proc.make_branch import main as make_branch_main


def _run_pr_survey(module, pass_dir):
    from lokay.passkit.support import is_manual_pr

    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    by = {}
    actions = list(working.get("actions") or [])
    for repo in begin.get("repos") or []:
        out = module._run(module.p_list_prs.main, ["--repo", repo])
        rows = list(out.get("prs") or []) if out.get("ok") else []
        by[repo] = rows
        actions.append({"step": "list_prs", "repo": repo, **out})
    working.update(
        actions=actions,
        prs_by_repo=by,
        remaining_prs=sum(len(v) for v in by.values()),
        actionable_prs=sum(not is_manual_pr(x) for v in by.values() for x in v),
        manual_prs=sum(is_manual_pr(x) for v in by.values() for x in v),
        pr_survey_failed=[],
    )
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    return {"ok": True}


def _run_closeout(module, pass_dir):
    from lokay.passkit.support import is_manual_pr

    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    prs = dict(working.get("prs_by_repo") or {})
    actions = list(working.get("actions") or [])
    merged = []
    needs = pending = green = limbo = progress = 0
    for repo, rows in prs.items():
        kept = []
        for pr in rows:
            if is_manual_pr(pr):
                kept.append(pr)
                continue
            checks = module._run(
                module.p_checks.main, ["--repo", repo, "--pr", str(pr["number"])]
            )
            status = str(checks.get("status") or "")
            if status == "pending":
                pending += 1
                kept.append(pr)
                continue
            if status == "failed":
                needs += 1
                module.compose_pr_repair(
                    config_path=None,
                    repo=repo,
                    pr_number=pr["number"],
                    branch=pr.get("head_ref", ""),
                    live=True,
                )
                kept.append(pr)
                continue
            tri = module.compose_pr_triage(
                config_path=None,
                repo=repo,
                pr_number=pr["number"],
                branch=pr.get("head_ref", ""),
                live=True,
            )
            actions.append({"step": "pr_triage", "pr": pr["number"], **tri})
            if tri.get("skipped"):
                if tri.get("repairable"):
                    needs += 1
                    rep = module.compose_pr_repair(
                        config_path=None,
                        repo=repo,
                        pr_number=pr["number"],
                        branch=pr.get("head_ref", ""),
                        live=True,
                        review=tri.get("review") or {},
                    )
                    actions.append(
                        {"step": "pr_review_repair", "pr": pr["number"], **rep}
                    )
                else:
                    limbo += 1
                kept.append(pr)
            else:
                progress += 1
                merged.append(repo)
        prs[repo] = kept
    working.update(
        actions=actions,
        prs_by_repo=prs,
        remaining_prs=sum(len(v) for v in prs.values()),
        actionable_prs=sum(not is_manual_pr(p) for v in prs.values() for p in v),
        manual_prs=sum(is_manual_pr(p) for v in prs.values() for p in v),
        needs_repair=needs,
        pending_checks=pending,
        mergeable_green=green,
        review_limbo=limbo,
        merged_this_pass=merged,
        progress=int(working.get("progress") or 0) + progress,
    )
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    return {"ok": True}


def _run_inbox(module, pass_dir):
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    by = {}
    issues = {}
    for repo in begin.get("repos") or []:
        try:
            out = module._run(module.p_list_inbox.main, ["--repo", repo])
        except AssertionError:
            out = {"ok": True, "issues": []}
        rows = list(out.get("issues") or []) if out.get("ok") else []
        by[repo] = len(rows)
        issues[repo] = rows
    working.update(
        inbox_by_repo=by,
        inbox_issues_by_repo=issues,
        remaining_inbox=sum(by.values()),
        inbox_survey_failed=[],
    )
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    return {"ok": True}


def test_load_example(tmp_path: Path, monkeypatch):
    # File values only — do not inherit LaunchAgent lokay env.
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
    """bool('false') is True in Python — quoted YAML must not arm the lokay."""
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
    """Quality gate: lokay must not merge without a structured reviewer."""
    from pathlib import Path

    from lokay.config import load_config

    monkeypatch.delenv("LOKAY_REQUIRE_LLM_REVIEW", raising=False)
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    assert cfg.require_llm_review is True


def test_committed_live_config_keeps_serial_issue_delivery_budget(monkeypatch):
    """Production follows the documented one-ticket-at-a-time contract."""
    from pathlib import Path

    from lokay.config import load_config

    for name in ("LOKAY_MAX_ISSUE_TO_PR_PER_PASS", "LOKAY_MAX_ISSUES_PER_TICK"):
        monkeypatch.delenv(name, raising=False)
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    assert cfg.max_issue_to_pr_per_pass == 1
    assert cfg.max_issues_per_tick == 1


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


def test_env_overrides_enable_live_lokay(tmp_path: Path, monkeypatch):
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


def test_pr_review_config_requires_pinned_plugin_provider_and_sandbox(tmp_path: Path):
    cfg = Config(
        mode="live",
        merge_enabled=True,
        repos=[RepoConfig(name="a/b", clone_path=tmp_path)],
        require_llm_review=True,
    )
    errors = cfg.validate()
    assert any("plugin command and args" in item for item in errors)
    assert any("provider and model" in item for item in errors)
    assert any("pinned pr_review binary" in item for item in errors)
    assert any("OS sandbox" in item for item in errors)
    assert any("config manifest" in item for item in errors)
    assert any("credential environment allowlist" in item for item in errors)

    sandbox_profile = tmp_path / "review.sb"
    sandbox_profile.write_text("sandbox profile")
    ocr_config = tmp_path / "ocr.json"
    ocr_config.write_text("{}")
    (tmp_path / "config-manifest.json").write_text("{}")
    configured = Config(
        mode="live",
        merge_enabled=True,
        repos=[RepoConfig(name="a/b", clone_path=tmp_path)],
        pr_review_plugin_command="lokay-review-opencode-plugin",
        pr_review_plugin_args=["--max-input-bytes", "4194304"],
        pr_review_provider="provider-a",
        pr_review_model="model-a",
        pr_review_config_sha256="c" * 64,
        pr_review_ocr_config=ocr_config,
        pr_review_manifest=tmp_path / "config-manifest.json",
        pr_review_sandbox_profile=sandbox_profile,
        pr_review_binary=tmp_path / "ocr",
        pr_review_binary_sha256="a" * 64,
        pr_review_rule_file=tmp_path / "rule.json",
        pr_review_tools_file=tmp_path / "tools.json",
        pr_review_sandbox_command=["sandbox-exec", "--"],
        pr_review_provider_env=["OCR_PROVIDER_KEY"],
    )
    assert configured.validate() == []


def test_pr_review_config_rejects_github_credentials_and_unknown_pin(tmp_path: Path):
    cfg = Config(
        repos=[RepoConfig(name="a/b", clone_path=tmp_path)],
        pr_review_provider_env=["OCR_PROVIDER_KEY", "GH_TOKEN"],
        pr_review_binary_version="v1.13.0",
    )
    errors = cfg.validate()
    assert any("forbidden name" in item for item in errors)
    assert any("pinned to v1.12.7" in item for item in errors)


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
        "--approve",
        "--no-session",
    ]
    cfg = Config(
        agent="pi",
        agent_command="pi",
        agent_args=list(args),
        timeout_seconds=99,
    )
    argv = build_agent_argv(cfg, worktree=Path("/tmp/wt"), prompt="fix it")
    assert argv == [
        "pi",
        "-p",
        "fix it",
        "--approve",
        "--no-session",
    ]
    assert "--model" not in argv
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


def test_lokay_offline_one_pass(tmp_path: Path, monkeypatch):
    from lokay.compose.run import compose_run

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
    monkeypatch.setattr(
        "lokay.proc.product_entry_subflow.run",
        lambda **kwargs: {"ok": True, "health": "offline", "passes": 1},
    )
    result = compose_run(config_path=str(cfg_path), live=False, max_passes=3)
    assert result.get("health") == "offline"
    assert result.get("passes") == 1


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
