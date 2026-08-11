from pathlib import Path

import pytest

from lokay import preflight
from lokay.compose import tick


@pytest.fixture(autouse=True)
def _clear_health_lease_environment(monkeypatch):
    monkeypatch.delenv("LOKAY_HEALTH_LEASE", raising=False)
    monkeypatch.delenv("LOKAY_HEALTH_LEASE_PATH", raising=False)


def _config(tmp_path: Path, *, min_free_gb: float = 0) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(
        f"""
mode: live
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: true
  command: omp
  args: ["-p", "{{prompt}}"]
limits:
  min_free_gb: {min_free_gb}
worktrees:
  root: {tmp_path / 'runtime' / 'worktrees'}
state:
  path: {tmp_path / 'runtime' / 'state' / 'events.jsonl'}
""",
        encoding="utf-8",
    )
    return path


def _host_ok(monkeypatch):
    monkeypatch.setattr(preflight.shutil, "which", lambda command: "/usr/bin/gh")
    monkeypatch.setattr(
        preflight.subprocess,
        "run",
        lambda *args, **kwargs: type("Completed", (), {"returncode": 0})(),
    )


def test_preflight_repairs_locale_and_runtime_directories(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    monkeypatch.delenv("LANG", raising=False)
    monkeypatch.setenv("LOKAY_LOG_DIR", str(tmp_path / "runtime" / "logs"))
    _host_ok(monkeypatch)

    result = preflight.run_preflight(str(cfg))

    assert result["ok"] is True, result
    assert {repair["kind"] for repair in result["repairs"]} == {
        "set_process_locale",
        "create_runtime_directories",
    }
    assert (tmp_path / "runtime" / "logs").is_dir()
    assert result["repairs"][0]["value"] == "[redacted]"


def test_preflight_fails_closed_when_github_unavailable(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setattr(preflight.shutil, "which", lambda command: None)

    result = preflight.run_preflight(str(cfg))

    assert result["ok"] is False
    finding = next(item for item in result["findings"] if item["name"] == "github_authentication")
    assert finding["ok"] is False
    assert all(len(item["detail"]) <= 240 for item in result["findings"])


def test_failed_preflight_blocks_every_product_atom(monkeypatch):
    monkeypatch.delenv("LOKAY_HEALTH_LEASE", raising=False)
    monkeypatch.setattr(tick, "health_lease_status", lambda: (False, "token_missing"))
    monkeypatch.setattr(
        tick,
        "run_preflight",
        lambda *args, **kwargs: {"ok": False, "health": "preflight_failed"},
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("product atom ran behind failed preflight")

    monkeypatch.setattr(tick, "_run", forbidden)
    result = tick.compose_tick(config_path="does-not-matter", live=True)

    assert result["ok"] is False
    assert result["executed"] is False
    assert result["actions"] == []
    assert result["health"] == "preflight_failed"


def test_inherited_lease_skips_duplicate_tick_preflight(monkeypatch):
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "a" * 64)
    monkeypatch.setattr(tick, "health_lease_status", lambda: (True, "ok"))
    monkeypatch.setattr(
        tick,
        "run_preflight",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("duplicate preflight")),
    )
    monkeypatch.setattr(
        tick,
        "load_cfg",
        lambda namespace: (_ for _ in ()).throw(RuntimeError("past preflight")),
    )

    with pytest.raises(RuntimeError, match="past preflight"):
        tick.compose_tick(config_path="config.yaml", live=True)


def test_nested_run_preflight_reuses_valid_inherited_lease(monkeypatch):
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "a" * 64)
    monkeypatch.setattr(preflight, "health_lease_status", lambda: (True, "ok"))
    monkeypatch.setattr(
        preflight,
        "_check",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("nested host checks")),
    )

    result = preflight.run_preflight("config.yaml")

    assert result["ok"] is True
    assert result["lease"] is True


def test_nested_run_preflight_rejects_invalid_inherited_lease(monkeypatch):
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "a" * 64)
    monkeypatch.setattr(preflight, "health_lease_status", lambda: (False, "expired"))
    monkeypatch.setattr(
        preflight,
        "_check",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("nested host checks")),
    )

    result = preflight.run_preflight("config.yaml")

    assert result["ok"] is False
    assert result["lease_reason"] == "expired"


def test_rejected_inherited_tick_lease_is_not_reissued(monkeypatch):
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "a" * 64)
    monkeypatch.setattr(
        tick, "health_lease_status", lambda: (False, "lease_unavailable_FileNotFoundError")
    )
    monkeypatch.setattr(
        tick,
        "run_preflight",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("nested preflight")),
    )

    result = tick.compose_tick(config_path="config.yaml", live=True)

    assert result["ok"] is False
    assert result["preflight"]["lease_reason"] == "lease_unavailable_FileNotFoundError"


def test_no_repair_keeps_missing_locale_unhealthy(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    monkeypatch.delenv("LANG", raising=False)
    _host_ok(monkeypatch)

    result = preflight.run_preflight(str(cfg), remediate=False)

    assert result["ok"] is False
    assert result["repairs"] == []
    assert next(item for item in result["findings"] if item["name"] == "required_environment")["ok"] is False


def test_real_os_lock_rejects_competitor(tmp_path):
    import subprocess, sys
    lock = tmp_path / "run.lock"
    assert preflight.acquire_run_lock(lock) is True
    code = "from pathlib import Path; from lokay.preflight import acquire_run_lock; raise SystemExit(0 if acquire_run_lock(Path(%r)) else 9)" % str(lock)
    child = subprocess.run([sys.executable, "-c", code], env={**__import__('os').environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src")})
    assert child.returncode == 9


def test_unsafe_symlink_runtime_path_is_not_repaired(tmp_path, monkeypatch):
    target = tmp_path / "target"; target.mkdir()
    link = tmp_path / "linked"; link.symlink_to(target, target_is_directory=True)
    cfg = _config(tmp_path)
    monkeypatch.setenv("LOKAY_LOG_DIR", str(link / "logs"))
    monkeypatch.setenv("LANG", "C.UTF-8"); _host_ok(monkeypatch)
    result = preflight.run_preflight(str(cfg))
    assert result["ok"] is False
    assert not (target / "worktrees").exists()


def test_executor_unavailable_closes_gate(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setattr(preflight.shutil, "which", lambda command: "/gh" if command == "gh" else None)
    monkeypatch.setattr(preflight.subprocess, "run", lambda *a, **kw: type("C", (), {"returncode": 0})())
    result = preflight.run_preflight(str(cfg))
    assert result["ok"] is False
    assert next(x for x in result["findings"] if x["name"] == "executor_availability")["ok"] is False
    assert Path(result["local_incident"]).is_file()


def test_direct_live_mutation_uses_health_gate(tmp_path, monkeypatch):
    from lokay.proc import _common
    from lokay.config import Config
    cfg = Config(mode="live", config_path=tmp_path / "config.yaml")
    monkeypatch.setattr(preflight, "require_healthy", lambda path: (_ for _ in ()).throw(RuntimeError("blocked")))
    import pytest
    with pytest.raises(RuntimeError, match="blocked"):
        _common.mutations_allowed(live_flag=True, cfg=cfg)


def test_inherited_health_lease_allows_child_behind_parent_lock(tmp_path, monkeypatch):
    import subprocess, sys, os
    monkeypatch.setenv("HOME", str(tmp_path))
    lock = tmp_path / ".lokay" / "mill.lock"
    assert preflight.acquire_run_lock(lock)
    preflight.issue_health_lease()
    code = "from lokay.preflight import require_healthy; require_healthy('missing-would-fail'); print('mutated')"
    child = subprocess.run(
        [sys.executable, "-c", code],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src")},
        capture_output=True, text=True,
    )
    assert child.returncode == 0, child.stderr
    assert child.stdout.strip() == "mutated"
    preflight.revoke_health_lease()


def test_health_lease_path_survives_changed_home(tmp_path, monkeypatch):
    original_home = tmp_path / "owner"
    monkeypatch.setenv("HOME", str(original_home))
    preflight.issue_health_lease()
    lease_path = original_home / ".lokay" / "health-lease"
    assert __import__("os").environ["LOKAY_HEALTH_LEASE_PATH"] == str(lease_path)

    monkeypatch.setenv("HOME", str(tmp_path / "child-home"))

    assert preflight._lease_path() == lease_path
    preflight.revoke_health_lease()


def test_default_health_lease_covers_long_agent_pass(tmp_path, monkeypatch):
    import json, time

    monkeypatch.setenv("HOME", str(tmp_path))
    preflight.issue_health_lease()
    record = json.loads((tmp_path / ".lokay" / "health-lease").read_text())
    assert record["expires_at"] - int(time.time()) >= 7198


def test_health_lease_is_not_just_an_environment_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "a" * 64)
    assert preflight.has_health_lease() is False


def test_rejected_inherited_lease_does_not_run_or_replace_preflight(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "a" * 64)
    monkeypatch.setattr(
        preflight,
        "run_preflight",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("nested preflight")),
    )

    with pytest.raises(RuntimeError, match="lease=lease_unavailable_"):
        preflight.require_healthy("config.yaml")

    assert __import__("os").environ["LOKAY_HEALTH_LEASE"] == "a" * 64


def test_commit_and_push_dry_run_do_not_require_config(tmp_path, monkeypatch, capsys):
    from lokay.proc import commit_all, push_branch
    monkeypatch.delenv("LOKAY_CONFIG", raising=False)
    assert commit_all.main(["--worktree", str(tmp_path), "--message", "x"]) == 0
    assert push_branch.main(["--worktree", str(tmp_path), "--branch", "x"]) == 0


def test_expired_and_revoked_health_leases_fail(tmp_path, monkeypatch):
    import json, time
    monkeypatch.setenv("HOME", str(tmp_path))
    preflight.issue_health_lease()
    path = tmp_path / ".lokay" / "health-lease"
    record = json.loads(path.read_text())
    record["expires_at"] = int(time.time()) - 1
    path.write_text(json.dumps(record)); path.chmod(0o600)
    assert preflight.has_health_lease() is False
    preflight.revoke_health_lease()
    assert not path.exists()
    assert preflight.has_health_lease() is False


def test_nested_issue_guard_never_mints_lease(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LOKAY_DISABLE_HEALTH_LEASE_ISSUE", "1")

    preflight.issue_health_lease()

    assert not (tmp_path / ".lokay" / "health-lease").exists()
    assert "LOKAY_HEALTH_LEASE" not in __import__("os").environ


def test_child_cannot_replace_parent_health_lease(tmp_path, monkeypatch):
    import json

    monkeypatch.setenv("HOME", str(tmp_path))
    assert preflight.acquire_run_lock(tmp_path / ".lokay" / "mill.lock")
    preflight.issue_health_lease()
    path = tmp_path / ".lokay" / "health-lease"
    record = json.loads(path.read_text())

    preflight.issue_health_lease()

    assert json.loads(path.read_text()) == record
    assert int(record["owner_pid"]) == __import__("os").getpid()


def test_rejected_inherited_lease_cannot_be_replaced(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "a" * 64)

    with pytest.raises(RuntimeError, match="refusing to replace inherited health lease"):
        preflight.issue_health_lease()


def test_child_cannot_revoke_parent_health_lease(tmp_path, monkeypatch):
    import json

    monkeypatch.setenv("HOME", str(tmp_path))
    preflight.issue_health_lease()
    path = tmp_path / ".lokay" / "health-lease"
    parent_token = __import__("os").environ["LOKAY_HEALTH_LEASE"]
    record = json.loads(path.read_text())

    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "b" * 64)
    preflight.revoke_health_lease()

    assert path.exists()
    assert json.loads(path.read_text()) == record
    assert parent_token != "b" * 64


def test_dead_owner_health_lease_fails(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("HOME", str(tmp_path))
    preflight.issue_health_lease()
    path = tmp_path / ".lokay" / "health-lease"
    record = json.loads(path.read_text()); record["owner_pid"] = 99999999
    path.write_text(json.dumps(record)); path.chmod(0o600)
    assert preflight.has_health_lease() is False


def test_lease_issuance_rejects_preexisting_symlink(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setenv("HOME", str(tmp_path))
    lease_dir = tmp_path / ".lokay"; lease_dir.mkdir()
    victim = tmp_path / "victim"; victim.write_text("untouched")
    (lease_dir / "health-lease").symlink_to(victim)
    with pytest.raises(RuntimeError, match="unsafe existing health lease"):
        preflight.issue_health_lease()
    assert victim.read_text() == "untouched"
    assert (lease_dir / "health-lease").is_symlink()


def test_lease_atomic_publish_never_writes_swap_symlink_target(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setenv("HOME", str(tmp_path))
    lease_dir = tmp_path / ".lokay"; lease_dir.mkdir()
    victim = tmp_path / "victim"; victim.write_text("untouched")
    real_replace = preflight.os.replace
    def swap_then_replace(src, dst):
        Path(dst).symlink_to(victim)
        real_replace(src, dst)
    monkeypatch.setattr(preflight.os, "replace", swap_then_replace)
    preflight.issue_health_lease()
    assert victim.read_text() == "untouched"
    assert not (lease_dir / "health-lease").is_symlink()


def test_trusted_manifest_uses_packaged_copy_without_checkout(tmp_path, monkeypatch):
    installed = tmp_path / "site-packages" / "lokay"
    packaged = installed / "data" / "lokay.fala-package.toml"
    packaged.parent.mkdir(parents=True)
    packaged.write_text('[[correlation_paths]]\nid = "factory_pass"\n', encoding="utf-8")
    monkeypatch.setattr(preflight, "__file__", str(installed / "preflight.py"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LOKAY_FALA_PACKAGE", raising=False)

    assert preflight.trusted_fala_manifest() == packaged


def test_trusted_manifest_rejects_checkout_mismatch(tmp_path, monkeypatch):
    installed = tmp_path / "checkout" / "src" / "lokay"
    packaged = installed / "data" / "lokay.fala-package.toml"
    source = tmp_path / "checkout" / "fala" / "lokay.fala-package.toml"
    packaged.parent.mkdir(parents=True)
    source.parent.mkdir(parents=True)
    packaged.write_text('[[correlation_paths]]\nid = "packaged"\n', encoding="utf-8")
    source.write_text('[[correlation_paths]]\nid = "source"\n', encoding="utf-8")
    monkeypatch.setattr(preflight, "__file__", str(installed / "preflight.py"))

    with pytest.raises(RuntimeError, match="differ"):
        preflight.trusted_fala_manifest()


def test_unhealthy_preflight_does_not_issue_lease(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("LOKAY_LOG_DIR", str(tmp_path / "runtime" / "logs"))
    _host_ok(monkeypatch)
    monkeypatch.setattr(
        preflight.shutil,
        "which",
        lambda command: None if command == "omp" else f"/usr/bin/{command}",
    )
    issued = []
    monkeypatch.setattr(preflight, "issue_health_lease", lambda: issued.append(True))

    result = preflight.run_preflight(str(cfg))

    assert result["ok"] is False
    assert next(
        item for item in result["findings"] if item["name"] == "executor_availability"
    )["ok"] is False
    assert issued == []


def test_smoke_valid_alternate_manifest_is_untrusted_carrier(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    alternate = tmp_path / "malicious.toml"
    alternate.write_text('correlation_paths = [{ id = "evil" }]')
    monkeypatch.setenv("LOKAY_FALA_PACKAGE", str(alternate))
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("LOKAY_LOG_DIR", str(tmp_path / "runtime" / "logs"))
    _host_ok(monkeypatch)
    issued = []
    monkeypatch.setattr(preflight, "issue_health_lease", lambda: issued.append(True))
    result = preflight.run_preflight(str(cfg))
    assert result["carrier_ok"] is False
    assert issued == []
    assert next(x for x in result["findings"] if x["name"] == "fala_manifest_provenance")["ok"] is False
