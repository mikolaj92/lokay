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
        {
            "lease_ok": None,
            "lease_reason": "not_observed",
            "run_active": True,
            "run_observation_reason": "active_run",
            "run_lease_path": "/state/health-lease-1-x",
        },
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
        and out["lease_ok"] is None
        and out["run_active"] is True
        and out["run_lease_path"] == "/state/health-lease-1-x"
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


def test_status_discovers_active_per_run_lease_without_inherited_capability(
    tmp_path, monkeypatch
):
    import fcntl
    import json
    import os
    import time

    from lokay.proc.read_status_lease import read

    state = tmp_path / "state"
    state.mkdir()
    lock = state / "mill.lock"
    held = lock.open("a+")
    fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    lease = state / "health-lease-123-deadbeef"
    lease.write_text(
        json.dumps(
            {
                "owner_pid": os.getpid(),
                "lock_path": str(lock.absolute()),
                "issued_at": int(time.time()),
                "expires_at": int(time.time()) + 60,
                "token_sha256": "0" * 64,
            }
        )
    )
    lease.chmod(0o600)
    monkeypatch.delenv("LOKAY_HEALTH_LEASE", raising=False)
    monkeypatch.delenv("LOKAY_HEALTH_LEASE_PATH", raising=False)

    out = read({"state_path": str(state / "events.jsonl")})

    assert out["lease_ok"] is None
    assert out["lease_reason"] == "not_observed"
    assert out["run_active"] is True
    assert out["run_observation_reason"] == "active_run"
    assert out["run_lease_path"] == str(lease)
    held.close()


def test_status_lease_observation_ignores_dangling_candidate(tmp_path, monkeypatch):
    from lokay.proc.read_status_lease import read

    state = tmp_path / "state"
    state.mkdir()
    (state / "health-lease-dead-link").symlink_to(state / "missing")
    monkeypatch.delenv("LOKAY_HEALTH_LEASE", raising=False)
    monkeypatch.delenv("LOKAY_HEALTH_LEASE_PATH", raising=False)

    out = read({"state_path": str(state / "events.jsonl")})

    assert out["run_active"] is False
    assert out["run_observation_reason"] == "inactive"


def test_status_lease_observation_does_not_create_missing_lock(tmp_path, monkeypatch):
    from lokay.proc.read_status_lease import read

    state = tmp_path / "state"
    state.mkdir()
    lock = state / "mill.lock"
    monkeypatch.delenv("LOKAY_HEALTH_LEASE", raising=False)
    monkeypatch.delenv("LOKAY_HEALTH_LEASE_PATH", raising=False)

    out = read({"state_path": str(state / "events.jsonl")})

    assert out["run_active"] is False
    assert not lock.exists()


def test_status_lease_observation_ignores_insecure_record(tmp_path, monkeypatch):
    import fcntl
    import json
    import os
    import time

    from lokay.proc.read_status_lease import read

    state = tmp_path / "state"
    state.mkdir()
    lock = state / "mill.lock"
    held = lock.open("a+")
    fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    lease = state / "health-lease-1-insecure"
    lease.write_text(json.dumps({
        "owner_pid": os.getpid(),
        "lock_path": str(lock.absolute()),
        "expires_at": int(time.time()) + 60,
        "token_sha256": "0" * 64,
    }))
    lease.chmod(0o644)
    monkeypatch.delenv("LOKAY_HEALTH_LEASE", raising=False)
    monkeypatch.delenv("LOKAY_HEALTH_LEASE_PATH", raising=False)

    out = read({"state_path": str(state / "events.jsonl")})

    assert out["run_active"] is False
    held.close()
