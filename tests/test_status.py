"""DoD status: mill_ready and blockers."""

from pathlib import Path

from lokay.cli import build_parser
from lokay.compose.status import compose_status


def _write_cfg(
    tmp_path: Path,
    *,
    mode: str,
    executor: bool,
    merge: bool,
    k: int = 1,
    repos: tuple[str, ...] = ("mikolaj92/lokay",),
) -> Path:
    cfg_path = tmp_path / "config.yaml"
    repo_yaml = "\n".join(
        f"  - name: {repo}\n    clone_path: {tmp_path / repo.split('/')[-1]}"
        for repo in repos
    )
    cfg_path.write_text(
        f"""
mode: {mode}
repos:
{repo_yaml}
executor:
  enabled: {str(executor).lower()}
  agent: grok
  command: grok
  args: ["{{prompt}}"]
merge:
  enabled: {str(merge).lower()}
  require_checks: true
limits:
  max_issue_to_pr_per_pass: {k}
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    return cfg_path


def test_readiness_reports_only_hard_config_blockers():
    from lokay.proc.classify_status_readiness import classify

    out = classify(
        {
            "mode": "dry-run",
            "executor_enabled": False,
            "merge_enabled": False,
            "require_checks": True,
            "require_llm_review": True,
        }
    )
    assert (
        out["mill_ready"] is False
        and len(out["blockers"]) == 3
        and any("require_checks" in x for x in out["policy_notes"])
    )


def test_require_checks_is_policy_not_hard_blocker():
    from lokay.proc.classify_status_readiness import classify

    out = classify(
        {
            "mode": "live",
            "executor_enabled": True,
            "merge_enabled": True,
            "require_checks": True,
            "require_llm_review": True,
        }
    )
    assert out["mill_ready"] is True and out["blockers"] == []


def test_snapshot_reducer_reads_last_receipt_without_survey():
    from lokay.proc.reduce_status_snapshot import reduce

    config = {
        "config": "c",
        "mode": "live",
        "executor_enabled": True,
        "agent": "a",
        "incident_repo": "i",
        "merge_enabled": True,
        "require_checks": True,
        "require_llm_review": True,
        "max_issue_to_pr_per_pass": 1,
        "repos": [{"name": "a/b", "enabled": True, "clone_path": "/x"}],
    }
    receipt = {
        "health": "repairing",
        "idle": False,
        "remaining": {"ready": 1, "by_repo": [{"repo": "a/b", "ready": 1}]},
        "human_residuals": {"count": 2},
    }
    out = reduce(
        config,
        {"mill_ready": True, "blockers": [], "policy_notes": []},
        {"missing_clones": []},
        {"lease_ok": True, "lease_reason": "ok"},
        {"receipt": receipt},
        {"graphs": ["factory_pass"]},
        {"preflight": None},
    )["snapshot"]
    assert (
        out["survey"] is False
        and out["snapshot"] is True
        and out["health"] == "repairing"
        and out["by_repo"][0]["repo"] == "a/b"
        and out["human_residuals"]["count"] == 2
    )


def test_status_terminal_fails_only_when_not_live_ready():
    from lokay.proc.status_snapshot_terminal import terminal

    bad = terminal({"snapshot": {"mill_ready": False}})["result"]
    good = terminal({"snapshot": {"mill_ready": True}})["result"]
    assert bad["ok"] is False and "error" in bad and good["ok"] is True


def test_cli_status_flags_wiring():
    parser = build_parser()
    assert (
        parser.parse_args(["status", "--local"]).local is True
        and parser.parse_args(["status", "--human"]).human is True
    )


def test_status_human_mailbox_remains_explicit_exception_view(tmp_path, monkeypatch):
    cfg = _write_cfg(tmp_path, mode="live", executor=True, merge=True)
    monkeypatch.setattr(
        "lokay.compose.status.compose_human_mailbox",
        lambda **k: {
            "ok": True,
            "kind": "human_mailbox",
            "mill_blocked": False,
            "count": 1,
            "items": [],
        },
    )
    result = compose_status(config_path=str(cfg), human=True)
    assert result["ok"] is True and result["mill_blocked"] is False


def test_status_facade_does_not_import_or_run_product_tick():
    import inspect

    from lokay.compose import status

    source = inspect.getsource(status)
    assert "compose_tick" not in source and "write_pass_receipt" not in source


def test_mill_daemon_does_not_override_configured_executor_metadata():
    script = (
        Path(__file__).resolve().parents[1] / "scripts/lokay-mill-daemon.sh"
    ).read_text()
    assert "export LOKAY_AGENT=" not in script and "LOKAY_AGENT:-grok" not in script


def test_mill_daemon_does_not_default_require_checks():
    script = (
        Path(__file__).resolve().parents[1] / "scripts/lokay-mill-daemon.sh"
    ).read_text()
    assert (
        "LOKAY_REQUIRE_CHECKS:-1" not in script
        and "export LOKAY_REQUIRE_CHECKS=" not in script
    )
