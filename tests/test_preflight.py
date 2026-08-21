from pathlib import Path
import json
import os
import time
from types import SimpleNamespace

import pytest

from lokay import preflight
from lokay.compose import tick


@pytest.fixture(autouse=True)
def _clear_health_lease_environment(request):
    """Keep lease env hermetic across tests.

    ``issue_health_lease`` writes ``os.environ`` directly, and tests also use
    ``monkeypatch.setenv`` for lease tokens. Clear before and after every test,
    after monkeypatch teardown, so nothing leaks into later modules.
    """
    import os

    def _clear() -> None:
        os.environ.pop("LOKAY_DISABLE_HEALTH_LEASE_ISSUE", None)
        os.environ.pop("LOKAY_HEALTH_LEASE", None)
        os.environ.pop("LOKAY_HEALTH_LEASE_PATH", None)

    _clear()
    # Run after function-scoped monkeypatch undos for this test.
    request.addfinalizer(_clear)


def _config(tmp_path: Path, *, min_free_gb: float = 0) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(
        f"""
mode: live
repos:
  - name: mikolaj92/lokay
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


def _auth_ok(monkeypatch):
    from lokay import preflight_checks

    ok = type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    real_which = preflight_checks.shutil.which

    def fake_which(command, path=None, **kwargs):
        if command == "gh":
            return "/usr/bin/gh"
        return real_which(command, path=path, **kwargs)

    # preflight.shutil is preflight_checks.shutil — do not stub every command.
    monkeypatch.setattr(preflight_checks.shutil, "which", fake_which)
    monkeypatch.setattr(preflight_checks.subprocess, "run", lambda *args, **kwargs: ok)
    return ok


def _host_ok(monkeypatch):
    ok = _auth_ok(monkeypatch)
    monkeypatch.setattr(preflight.shutil, "which", lambda command, **kwargs: "/usr/bin/gh")
    monkeypatch.setattr(preflight.subprocess, "run", lambda *args, **kwargs: ok)


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


def test_catalog_clone_check_ignores_product_repositories(tmp_path):
    from types import SimpleNamespace

    from lokay.preflight_checks import check_repository_catalog_clones

    product_clone = tmp_path / "Temida"
    lokay_clone = tmp_path / "lokay"
    product_clone.mkdir()
    cfg = SimpleNamespace(
        active_repos=lambda: [
            SimpleNamespace(name="mikolaj92/Temida", clone_path=product_clone),
            SimpleNamespace(name="mikolaj92/takt", clone_path=tmp_path / "takt"),
            SimpleNamespace(name="mikolaj92/lokay", clone_path=lokay_clone),
        ]
    )

    finding = check_repository_catalog_clones(cfg=cfg)

    assert finding["code"] == "missing_clones_allowed"
    lokay_clone.mkdir()
    assert check_repository_catalog_clones(cfg=cfg)["code"] == "ok"


def test_missing_catalog_clone_does_not_block_global_preflight(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    cfg.write_text(
        cfg.read_text().replace(
            f"clone_path: {tmp_path}", f"clone_path: {tmp_path / 'missing-clone'}"
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("LOKAY_LOG_DIR", str(tmp_path / "runtime" / "logs"))
    _host_ok(monkeypatch)

    result = preflight.run_preflight(str(cfg))

    assert result["ok"] is True, result
    finding = next(
        item
        for item in result["findings"]
        if item["name"] == "repository_catalog_clones"
    )
    assert finding["ok"] is True
    assert finding["code"] == "missing_clones_allowed"


def test_preflight_fails_closed_when_github_unavailable(tmp_path, monkeypatch):
    from lokay import preflight_checks

    cfg = _config(tmp_path)
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setattr(preflight.shutil, "which", lambda command, **kwargs: None)
    monkeypatch.setattr(preflight_checks.shutil, "which", lambda command, **kwargs: None)

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


def test_validation_lease_is_bound_to_contended_custom_state_lock(tmp_path, monkeypatch):
    import os
    import subprocess
    import sys

    real_run = subprocess.run
    cfg = _config(tmp_path)
    state_dir = tmp_path / "runtime" / "state"
    for path in (state_dir, tmp_path / "runtime" / "worktrees", tmp_path / "runtime" / "logs"):
        path.mkdir(parents=True)
    custom_lock = state_dir / "mill.lock"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("LOKAY_LOG_DIR", str(tmp_path / "runtime" / "logs"))
    _host_ok(monkeypatch)

    assert preflight.acquire_run_lock(custom_lock)
    preflight.issue_health_lease(lock_path=custom_lock)
    competitor = real_run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; from lokay.preflight import acquire_run_lock; "
            f"raise SystemExit(0 if acquire_run_lock(Path({str(custom_lock)!r})) else 9)",
        ],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src")},
        check=False,
    )
    assert competitor.returncode == 9

    result = preflight.run_preflight(
        str(cfg), remediate=False, validate_inherited_lease=True
    )
    assert result["ok"] is True, result
    assert next(x for x in result["findings"] if x["name"] == "singleton_overlap")["ok"]
    preflight.revoke_health_lease()

    # A lease for the legacy HOME lock must not bypass this config's lock.
    home_lock = tmp_path / ".lokay" / "mill.lock"
    assert preflight.acquire_run_lock(home_lock)
    preflight.issue_health_lease(lock_path=home_lock)
    mismatched = preflight.run_preflight(
        str(cfg), remediate=False, validate_inherited_lease=True
    )
    assert mismatched["ok"] is False
    assert mismatched["lease_reason"] == "lock_path_mismatch"
    preflight.revoke_health_lease()


def test_validation_accepts_old_schema_lease_from_running_daemon(tmp_path, monkeypatch):
    import json
    import os
    import subprocess
    import sys

    cfg = _config(tmp_path)
    state_dir = tmp_path / "runtime" / "state"
    for path in (state_dir, tmp_path / "runtime" / "worktrees", tmp_path / "runtime" / "logs"):
        path.mkdir(parents=True)
    daemon_lock = tmp_path / ".lokay" / "mill.lock"
    configured_lock = state_dir / "mill.lock"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("LOKAY_LOG_DIR", str(tmp_path / "runtime" / "logs"))
    _host_ok(monkeypatch)

    # The old daemon owns its HOME lock and acquired the configured lock while
    # running preflight, but its lease record predates the lock_path field.
    assert preflight.acquire_run_lock(daemon_lock)
    assert preflight.acquire_run_lock(configured_lock)
    preflight.issue_health_lease()
    lease_path = Path(__import__("os").environ["LOKAY_HEALTH_LEASE_PATH"])
    record = json.loads(lease_path.read_text())
    record.pop("lock_path")
    lease_path.write_text(json.dumps(record))
    lease_path.chmod(0o600)

    child = subprocess.run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; from lokay.preflight import health_lease_status; "
            f"raise SystemExit(0 if health_lease_status(lock_path=Path({str(configured_lock)!r}))[0] else 9)",
        ],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src")},
        check=False,
    )
    assert child.returncode == 0

    result = preflight.run_preflight(
        str(cfg), remediate=False, validate_inherited_lease=True
    )

    assert result["ok"] is True, result
    assert next(x for x in result["findings"] if x["name"] == "singleton_overlap")["ok"]
    preflight.revoke_health_lease()


@pytest.mark.parametrize(
    "failed",
    [
        [preflight._finding("singleton_overlap", False, "contended")],
        [
            preflight._finding(
                "writable_runtime_paths", False, "unsafe_or_unwritable"
            )
        ],
        [
            preflight._finding(
                "repository_catalog_clones", False, "missing_clone"
            ),
            preflight._finding("singleton_overlap", False, "contended"),
        ],
    ],
)
def test_github_incident_refuses_operational_inventory_failures(
    monkeypatch, failed
):
    monkeypatch.setattr(
        preflight.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("GitHub mutation attempted for operational inventory")
        ),
    )
    result = {
        "findings": [
            preflight._finding("github_authentication", True, "ok"),
            *failed,
        ]
    }

    assert preflight._github_incident(result) is None


def test_healthy_preflight_closes_open_incident_tickets(monkeypatch):
    """Stale preflight issues must not stay open after the mill is healthy."""
    closed: list[list[str]] = []

    def fake_run(argv, *args, **kwargs):
        cmd = list(argv)
        if cmd[:2] == ["gh", "api"]:
            payload = json.dumps(
                [
                    [
                        {
                            "number": 178,
                            "body": "<!-- lokay-preflight:7a069cefb68040e2 -->\nBounded checks failed",
                            "title": "Preflight failure 7a069cefb68040e2",
                        },
                        {
                            "number": 99,
                            "body": "ordinary product ticket",
                            "title": "fix mill",
                        },
                    ]
                ]
            )
            return type(
                "Completed",
                (),
                {"returncode": 0, "stdout": payload, "stderr": ""},
            )()
        if cmd[:3] == ["gh", "issue", "close"]:
            closed.append(cmd)
            return type(
                "Completed", (), {"returncode": 0, "stdout": "", "stderr": ""}
            )()
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    out = preflight._close_resolved_incidents("mikolaj92/lokay")
    assert out == {"ok": True, "closed": [178]}
    assert any(c[:4] == ["gh", "issue", "close", "178"] for c in closed)
    assert all("99" not in c for c in closed)


def test_empty_incident_probe_writes_stamp_and_skip_does_not_refresh(
    tmp_path, monkeypatch
):
    cfg = _config(tmp_path)
    from lokay.config import load_config

    loaded = load_config(str(cfg))
    stamp = preflight.incident_stamp_path(loaded)
    listed: list[int] = []

    def fake_run(argv, *args, **kwargs):
        cmd = list(argv)
        if cmd[:2] == ["gh", "api"]:
            listed.append(1)
            return type(
                "Completed",
                (),
                {"returncode": 0, "stdout": "[[]]", "stderr": ""},
            )()
        raise AssertionError(argv)

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    first = preflight._close_resolved_incidents("mikolaj92/lokay", loaded)
    assert first == {"ok": True, "closed": []}
    assert listed == [1]
    assert stamp is not None and stamp.is_file()
    mtime = stamp.stat().st_mtime
    second = preflight._close_resolved_incidents("mikolaj92/lokay", loaded)
    assert second == {
        "ok": True,
        "closed": [],
        "skipped": True,
        "reason": "recent_empty",
    }
    assert listed == [1]
    assert stamp.stat().st_mtime == mtime


def test_idle_leftover_incident_skip_outlives_leftover_probe(tmp_path, monkeypatch):
    """Idle leftover-incident skip outlives leftover-probe. Hosted factory_pass stays at 300s."""
    cfg = _config(tmp_path)
    from lokay.config import load_config

    loaded = load_config(str(cfg))
    stamp = preflight.incident_stamp_path(loaded)
    assert stamp is not None
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text("1", encoding="utf-8")
    leftover_age = time.time() - 301
    os.utime(stamp, (leftover_age, leftover_age))
    listed: list[int] = []

    def fake_run(argv, *args, **kwargs):
        cmd = list(argv)
        if cmd[:2] == ["gh", "api"]:
            listed.append(1)
            return type(
                "Completed",
                (),
                {"returncode": 0, "stdout": "[[]]", "stderr": ""},
            )()
        raise AssertionError(argv)

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    monkeypatch.delenv("LOKAY_LEFTOVER_PROBE_GH_OK", raising=False)
    hosted = preflight._close_resolved_incidents("mikolaj92/lokay", loaded)
    assert hosted.get("skipped") is not True
    assert listed == [1]
    leftover_age = time.time() - 301
    os.utime(stamp, (leftover_age, leftover_age))
    listed.clear()
    monkeypatch.setenv("LOKAY_LEFTOVER_PROBE_GH_OK", "1")
    idle = preflight._close_resolved_incidents("mikolaj92/lokay", loaded)
    assert idle == {
        "ok": True,
        "closed": [],
        "skipped": True,
        "reason": "recent_empty",
    }
    assert listed == []
    assert stamp.stat().st_mtime == leftover_age
    assert preflight.incident_recently_empty(stamp) is False
    assert preflight.incident_recently_empty(
        stamp, ttl=preflight.IDLE_INCIDENT_TTL_SECONDS
    ) is True
    src = Path(__file__).resolve().parents[1] / "src" / "lokay" / "preflight.py"
    assert "Idle leftover-incident skip outlives leftover-probe." in src.read_text(
        encoding="utf-8"
    )


def test_pytest_does_not_skip_leftover_incident_github_lists_using_the_mill_stamp(
    tmp_path, monkeypatch
):
    mill = tmp_path / ".lokay"
    mill.mkdir()
    stamp = mill / "preflight-incident-close.stamp"
    stamp.write_text("1", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv(
        "PYTEST_CURRENT_TEST",
        "test_pytest_does_not_skip_leftover_incident_github_lists_using_the_mill_stamp",
    )
    assert preflight.incident_recently_empty(stamp) is False
    listed: list[int] = []

    def fake_run(argv, *args, **kwargs):
        cmd = list(argv)
        if cmd[:2] == ["gh", "api"]:
            listed.append(1)
            return type(
                "Completed",
                (),
                {"returncode": 0, "stdout": "[[]]", "stderr": ""},
            )()
        raise AssertionError(argv)

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    cfg = SimpleNamespace(state_path=mill / "state.jsonl")
    out = preflight._close_resolved_incidents("mikolaj92/lokay", cfg)
    assert out.get("skipped") is not True
    assert listed == [1]
    hermetic = tmp_path / "preflight-incident-close.stamp"
    hermetic.write_text("1", encoding="utf-8")
    assert preflight.incident_recently_empty(hermetic) is True
    src = Path(__file__).resolve().parents[1] / "src" / "lokay" / "preflight.py"
    assert "Pytest must not skip leftover-incident GitHub lists using the mill stamp." in src.read_text(
        encoding="utf-8"
    )


def test_incident_probe_failure_does_not_write_stamp(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    from lokay.config import load_config

    loaded = load_config(str(cfg))
    stamp = preflight.incident_stamp_path(loaded)

    def fake_run(argv, *args, **kwargs):
        return type(
            "Completed", (), {"returncode": 1, "stdout": "", "stderr": "HTTP 429"}
        )()

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    out = preflight._close_resolved_incidents("mikolaj92/lokay", loaded)
    assert out == {"ok": True, "closed": []}
    assert stamp is not None and not stamp.exists()


def test_closing_an_incident_clears_the_empty_stamp(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    from lokay.config import load_config

    loaded = load_config(str(cfg))
    stamp = preflight.incident_stamp_path(loaded)
    assert stamp is not None
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text("stale", encoding="utf-8")
    stamp.touch()
    import os
    os.utime(stamp, (0, 0))

    def fake_run(argv, *args, **kwargs):
        cmd = list(argv)
        if cmd[:2] == ["gh", "api"]:
            payload = json.dumps(
                [
                    [
                        {
                            "number": 178,
                            "body": "<!-- lokay-preflight:7a069cefb68040e2 -->\nBounded checks failed",
                            "title": "Preflight failure 7a069cefb68040e2",
                        }
                    ]
                ]
            )
            return type(
                "Completed",
                (),
                {"returncode": 0, "stdout": payload, "stderr": ""},
            )()
        if cmd[:3] == ["gh", "issue", "close"]:
            return type(
                "Completed", (), {"returncode": 0, "stdout": "", "stderr": ""}
            )()
        raise AssertionError(argv)

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    out = preflight._close_resolved_incidents("mikolaj92/lokay", loaded)
    assert out == {"ok": True, "closed": [178]}
    assert not stamp.exists()


def test_daemon_healthy_preflight_closes_resolved_incidents(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("LOKAY_LOG_DIR", str(tmp_path / "runtime" / "logs"))
    _host_ok(monkeypatch)
    called: list[str] = []

    def fake_close(repo: str, cfg=None) -> dict:
        called.append(repo)
        return {"ok": True, "closed": [178]}

    monkeypatch.setattr(preflight, "_close_resolved_incidents", fake_close)
    result = preflight.run_preflight(str(cfg), issue_lease=True)
    assert result["ok"] is True
    assert called == ["mikolaj92/lokay"]
    assert result["resolved_incidents"]["closed"] == [178]


@pytest.mark.parametrize(
    "findings",
    [
        [preflight._finding("singleton_overlap", False, "contended")],
        [
            preflight._finding(
                "repository_catalog_clones", False, "missing_clone"
            ),
            preflight._finding("singleton_overlap", False, "contended"),
        ],
    ],
)
def test_singleton_contention_is_not_recorded_as_an_incident(
    monkeypatch, findings
):
    monkeypatch.setattr(
        preflight,
        "_check",
        lambda *args, **kwargs: (
            {
                "ok": False,
                "carrier_ok": False,
                "integrity_ok": True,
                "findings": findings,
            },
            None,
        ),
    )
    monkeypatch.setattr(
        preflight,
        "_persist_incident",
        lambda *args: (_ for _ in ()).throw(AssertionError("operational overlap incident")),
    )
    monkeypatch.setattr(
        preflight,
        "_github_incident",
        lambda result, cfg=None: (_ for _ in ()).throw(
            AssertionError("operational overlap issue")
        ),
    )

    result = preflight.run_preflight("config.yaml", remediate=False)

    assert result["ok"] is False
    assert result["health"] == "overlap"
    assert result["operational_overlap"] is True
    assert result["local_incident"] is None
    assert result["incident_url"] is None


def test_self_repair_validation_does_not_open_recursive_incident(monkeypatch):
    monkeypatch.setenv("LOKAY_SELF_REPAIR_VALIDATION", "1")
    monkeypatch.setattr(
        preflight,
        "_check",
        lambda *args, **kwargs: (
            {
                "ok": False,
                "carrier_ok": False,
                "integrity_ok": True,
                "findings": [
                    preflight._finding(
                        "singleton_overlap", False, "contended"
                    )
                ],
            },
            None,
        ),
    )
    monkeypatch.setattr(
        preflight,
        "_persist_incident",
        lambda *args: (_ for _ in ()).throw(AssertionError("recursive local incident")),
    )
    monkeypatch.setattr(
        preflight,
        "_github_incident",
        lambda result, cfg=None: (_ for _ in ()).throw(
            AssertionError("recursive GitHub incident")
        ),
    )

    result = preflight.run_preflight("config.yaml", remediate=False)

    assert result["ok"] is False
    assert result["local_incident"] is None
    assert result["incident_url"] is None


@pytest.mark.parametrize(
    "findings",
    [
        [preflight._finding("lokay_integrity", False, "python_syntax_invalid")],
        [
            preflight._finding("singleton_overlap", False, "contended"),
            preflight._finding("github_authentication", False, "unavailable"),
        ],
    ],
)
def test_self_repair_validation_reports_non_singleton_failures(monkeypatch, findings):
    monkeypatch.setenv("LOKAY_SELF_REPAIR_VALIDATION", "1")
    monkeypatch.setattr(
        preflight,
        "_check",
        lambda *args, **kwargs: (
            {
                "ok": False,
                "carrier_ok": False,
                "integrity_ok": False,
                "findings": findings,
            },
            None,
        ),
    )
    persisted = []
    published = []
    monkeypatch.setattr(
        preflight,
        "_persist_incident",
        lambda cfg, result: persisted.append(result) or Path("incident.json"),
    )
    monkeypatch.setattr(
        preflight,
        "_github_incident",
        lambda result, cfg=None: published.append(result)
        or "https://example.test/issues/1",
    )

    result = preflight.run_preflight("config.yaml", remediate=False)

    assert result["ok"] is False
    assert result["local_incident"] == "incident.json"
    assert result["incident_url"] == "https://example.test/issues/1"
    assert persisted == [result]
    assert published == [result]


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


def test_unavailable_runtime_path_does_not_open_github_issue(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    state_dir = tmp_path / "runtime" / "state"
    worktrees = tmp_path / "runtime" / "worktrees"
    state_dir.mkdir(parents=True)
    worktrees.mkdir(parents=True)
    target = tmp_path / "log-target"
    target.mkdir()
    unsafe_log_dir = tmp_path / "linked-logs"
    unsafe_log_dir.symlink_to(target, target_is_directory=True)
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("LOKAY_LOG_DIR", str(unsafe_log_dir / "unavailable"))
    monkeypatch.setattr(
        preflight.shutil, "which", lambda command, **kwargs: f"/usr/bin/{command}"
    )

    def allow_auth_only(args, **kwargs):
        if list(args)[:3] == ["gh", "api", "user"]:
            return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        raise AssertionError("GitHub mutation attempted for runtime-path failure")

    from lokay import preflight_checks

    monkeypatch.setattr(preflight.subprocess, "run", allow_auth_only)
    monkeypatch.setattr(preflight_checks.subprocess, "run", allow_auth_only)
    monkeypatch.setattr(preflight_checks.shutil, "which", lambda command, **kwargs: f"/usr/bin/{command}")

    result = preflight.run_preflight(str(cfg), remediate=False)

    assert result["ok"] is False
    assert {
        item["name"] for item in result["findings"] if not item["ok"]
    } == {"writable_runtime_paths", "disk_headroom"}
    assert result["incident_url"] is None


def test_executor_unavailable_closes_gate(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    monkeypatch.setenv("LANG", "C.UTF-8")
    _auth_ok(monkeypatch)
    monkeypatch.setattr(preflight.shutil, "which", lambda command, **kwargs: "/gh" if command == "gh" else None)
    monkeypatch.setattr(preflight.subprocess, "run", lambda *a, **kw: type("C", (), {"returncode": 0})())
    result = preflight.run_preflight(str(cfg))
    assert result["ok"] is False
    assert next(x for x in result["findings"] if x["name"] == "executor_availability")["ok"] is False
    assert Path(result["local_incident"]).is_file()


def test_preflight_repairs_daemon_path_for_pi_in_local_bin(tmp_path, monkeypatch):
    """Issue #15: preflight must find the configured Pi installation when the
    daemon process starts with launchd's system-only PATH."""
    cfg = _config(tmp_path)
    cfg.write_text(cfg.read_text().replace("command: omp", "command: pi"))
    user_bin = tmp_path / ".local" / "bin"
    user_bin.mkdir(parents=True)
    (user_bin / "pi").touch(mode=0o755)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("LANG", "C.UTF-8")
    _auth_ok(monkeypatch)
    real_which = preflight.shutil.which
    monkeypatch.setattr(preflight.shutil, "which", lambda command, **kwargs: "/gh" if command == "gh" else real_which(command, **kwargs))
    monkeypatch.setattr(preflight.subprocess, "run", lambda *a, **kw: type("C", (), {"returncode": 0})())

    result = preflight.run_preflight(str(cfg))

    assert result["ok"] is True, result
    assert __import__("os").environ["PATH"] == f"/usr/bin:/bin:{user_bin}"
    assert any(repair["kind"] == "extend_runtime_path" for repair in result["repairs"])
    finding = next(x for x in result["findings"] if x["name"] == "executor_availability")
    assert finding["ok"] is True
    assert finding["repaired"] is True


def test_preflight_repairs_service_path_for_mise_shimmed_executor(tmp_path, monkeypatch):
    """Issue #14: the mill daemon runs under a minimal launchd PATH while the
    executor (pi) lives in mise shims; preflight must expose it and release
    the gate with both incident findings healthy."""
    cfg = _config(tmp_path)
    shims = tmp_path / ".local" / "share" / "mise" / "shims"
    shims.mkdir(parents=True)
    (shims / "omp").touch(mode=0o755)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("LANG", "C.UTF-8")
    _auth_ok(monkeypatch)
    real_which = preflight.shutil.which
    monkeypatch.setattr(preflight.shutil, "which", lambda command, **kwargs: "/gh" if command == "gh" else real_which(command, **kwargs))
    monkeypatch.setattr(preflight.subprocess, "run", lambda *a, **kw: type("C", (), {"returncode": 0})())

    result = preflight.run_preflight(str(cfg))

    assert result["ok"] is True, result
    assert result["gate_released"] is True
    assert any(repair["kind"] == "extend_runtime_path" for repair in result["repairs"])
    executor = next(x for x in result["findings"] if x["name"] == "executor_availability")
    assert executor["ok"] is True
    assert executor["repaired"] is True
    # The other half of the incident pair (fala_smoke) stays healthy against
    # the real installed Fala and canonical manifest.
    assert next(x for x in result["findings"] if x["name"] == "fala_smoke")["ok"] is True


def test_preflight_repairs_service_path_for_pi_agent_install(tmp_path, monkeypatch):
    """Issue #15: find an executor installed by Pi's agent runtime."""
    cfg = _config(tmp_path)
    cfg.write_text(cfg.read_text().replace("command: omp", "command: pi"))
    agent_bin = tmp_path / ".pi" / "agent" / "bin"
    agent_bin.mkdir(parents=True)
    (agent_bin / "pi").touch(mode=0o755)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("LANG", "C.UTF-8")
    _auth_ok(monkeypatch)
    real_which = preflight.shutil.which
    monkeypatch.setattr(
        preflight.shutil,
        "which",
        lambda command, **kwargs: "/gh" if command == "gh" else real_which(command, **kwargs),
    )
    monkeypatch.setattr(
        preflight.subprocess,
        "run",
        lambda *a, **kw: type("C", (), {"returncode": 0})(),
    )

    result = preflight.run_preflight(str(cfg))

    assert result["ok"] is True, result
    assert __import__("os").environ["PATH"] == f"/usr/bin:/bin:{agent_bin}"
    assert any(repair["kind"] == "extend_runtime_path" for repair in result["repairs"])
    executor = next(x for x in result["findings"] if x["name"] == "executor_availability")
    assert executor["ok"] is True
    assert executor["repaired"] is True


def test_preflight_repairs_executor_from_login_home_when_home_is_service_fallback(
    tmp_path, monkeypatch
):
    """A daemon fallback HOME must not hide the account's executor install."""
    cfg = _config(tmp_path)
    cfg.write_text(cfg.read_text().replace("command: omp", "command: pi"))
    service_home = tmp_path / "service-home"
    login_home = tmp_path / "login-home"
    (login_home / ".local" / "bin").mkdir(parents=True)
    (login_home / ".local" / "bin" / "pi").touch(mode=0o755)
    monkeypatch.setenv("HOME", str(service_home))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("LOKAY_LOG_DIR", str(tmp_path / "runtime" / "logs"))
    monkeypatch.setattr(
        preflight.pwd,
        "getpwuid",
        lambda uid: type("Passwd", (), {"pw_dir": str(login_home)})(),
    )
    _auth_ok(monkeypatch)
    real_which = preflight.shutil.which
    monkeypatch.setattr(
        preflight.shutil,
        "which",
        lambda command, **kwargs: "/gh"
        if command == "gh"
        else real_which(command, **kwargs),
    )
    monkeypatch.setattr(
        preflight.subprocess,
        "run",
        lambda *args, **kwargs: type("C", (), {"returncode": 0})(),
    )

    result = preflight.run_preflight(str(cfg))

    assert result["ok"] is True, [item for item in result["findings"] if not item["ok"]]
    assert str(login_home / ".local" / "bin") in __import__("os").environ["PATH"]
    executor = next(x for x in result["findings"] if x["name"] == "executor_availability")
    assert executor["ok"] is True
    assert executor["repaired"] is True


def test_executor_path_repair_only_adds_directory_containing_command(tmp_path, monkeypatch):
    home = tmp_path / "home"
    user_bin = home / ".local" / "bin"
    shims = home / ".local" / "share" / "mise" / "shims"
    user_bin.mkdir(parents=True)
    shims.mkdir(parents=True)
    (shims / "omp").touch(mode=0o755)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    assert preflight._repair_runtime_path("omp") is True
    assert __import__("os").environ["PATH"] == f"/usr/bin:/bin:{shims}"


def test_executor_path_repair_preserves_existing_command_precedence(tmp_path, monkeypatch):
    home = tmp_path / "home"
    existing_bin = tmp_path / "existing"
    user_bin = home / ".local" / "bin"
    existing_bin.mkdir()
    user_bin.mkdir(parents=True)
    (existing_bin / "gh").touch(mode=0o755)
    (user_bin / "gh").touch(mode=0o755)
    (user_bin / "omp").touch(mode=0o755)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", str(existing_bin))

    assert preflight._repair_runtime_path("omp") is True
    assert preflight.shutil.which("gh") == str(existing_bin / "gh")


def test_executor_path_repair_with_empty_path_has_no_empty_entry(tmp_path, monkeypatch):
    home = tmp_path / "home"
    user_bin = home / ".local" / "bin"
    user_bin.mkdir(parents=True)
    (user_bin / "omp").touch(mode=0o755)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", "")

    assert preflight._repair_runtime_path("omp") is True
    assert __import__("os").environ["PATH"] == str(user_bin)
    assert "" not in __import__("os").environ["PATH"].split(__import__("os").pathsep)


def test_failed_executor_path_repair_does_not_mutate_path(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".local" / "bin").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    assert preflight._repair_runtime_path("missing-executor") is False
    assert __import__("os").environ["PATH"] == "/usr/bin:/bin"


def test_fala_smoke_reports_bounded_exception_class(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    _host_ok(monkeypatch)
    monkeypatch.setattr(preflight, "trusted_fala_manifest", lambda: (_ for _ in ()).throw(RuntimeError("secret detail")))

    result = preflight.run_preflight(str(cfg), remediate=False)

    finding = next(x for x in result["findings"] if x["name"] == "fala_smoke")
    assert finding["code"] == "unavailable_RuntimeError"
    assert "secret detail" not in finding["detail"]


def test_fala_smoke_requires_the_complete_lokay_workflow_manifest(tmp_path, monkeypatch):
    package = tmp_path / "incomplete.toml"
    package.write_text('[[correlation_paths]]\nid = "issue_to_pr"\n', encoding="utf-8")
    monkeypatch.setattr(preflight, "trusted_fala_manifest", lambda: package)

    ok, code = preflight._fala_smoke()

    assert ok is False
    assert code == "incompatible_api_or_manifest"


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

    assert preflight.acquire_run_lock(tmp_path / ".lokay" / "mill.lock")
    # Missing file + inherited token: restore the record, then mutate.
    preflight.require_healthy("config.yaml")
    assert preflight.has_health_lease() is True
    assert __import__("os").environ["LOKAY_HEALTH_LEASE"] == "a" * 64


def test_restored_lease_owner_does_not_need_mill_lock(tmp_path, monkeypatch):
    """Detached issue_to_pr outlives the mill lock; inherited token must still mutate."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "c" * 64)
    # No acquire_run_lock — mill tick already exited.
    preflight.require_healthy("config.yaml")
    assert preflight.has_health_lease() is True
    assert (tmp_path / ".lokay" / "health-lease").is_file()


def test_expired_inherited_lease_still_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "a" * 64)
    monkeypatch.setattr(preflight, "health_lease_status", lambda: (False, "expired"))
    with pytest.raises(RuntimeError, match="lease=expired"):
        preflight.require_healthy("config.yaml")


def test_commit_and_push_dry_run_do_not_require_config(tmp_path, monkeypatch, capsys):
    from lokay.proc import commit_all, push_branch
    monkeypatch.delenv("LOKAY_CONFIG", raising=False)
    assert commit_all.main(["--worktree", str(tmp_path), "--message", "x"]) == 0
    assert push_branch.main(["--repo", "mikolaj92/lokay", "--worktree", str(tmp_path), "--branch", "x"]) == 0


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


def test_dead_owner_inherited_token_is_restored(tmp_path, monkeypatch):
    """Mill pid in the lease record can be gone; same token must still push."""
    import json

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "f" * 64)
    monkeypatch.setenv("LOKAY_DISABLE_HEALTH_LEASE_ISSUE", "1")
    lease = tmp_path / ".lokay" / "health-lease"
    lease.parent.mkdir(parents=True)
    lease.write_text(
        json.dumps(
            {
                "token_sha256": __import__("hashlib").sha256(("f" * 64).encode()).hexdigest(),
                "owner_pid": 999_999_999,
                "lock_path": str(tmp_path / ".lokay" / "mill.lock"),
                "issued_at": 1,
                "expires_at": 2_000_000_000,
            }
        )
    )
    lease.chmod(0o600)
    preflight.require_healthy("config.yaml")
    assert preflight.has_health_lease() is True
    assert json.loads(lease.read_text())["owner_pid"] == __import__("os").getpid()


def test_disable_still_restores_inherited_token_file(tmp_path, monkeypatch):
    """Mill sets DISABLE=1 on the tree; detached children must rewrite a missing file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "e" * 64)
    monkeypatch.setenv("LOKAY_DISABLE_HEALTH_LEASE_ISSUE", "1")
    preflight.require_healthy("config.yaml")
    assert preflight.has_health_lease() is True
    assert (tmp_path / ".lokay" / "health-lease").is_file()


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
    import json
    import time

    monkeypatch.setenv("HOME", str(tmp_path))
    assert preflight.acquire_run_lock(tmp_path / ".lokay" / "mill.lock")
    preflight.issue_health_lease()
    path = tmp_path / ".lokay" / "health-lease"
    record = json.loads(path.read_text())
    record["expires_at"] = int(time.time()) - 1
    path.write_text(json.dumps(record))
    path.chmod(0o600)
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


def test_installed_manifest_ignores_unrelated_checkout_cwd(tmp_path, monkeypatch):
    installed = tmp_path / "site-packages" / "lokay"
    packaged = installed / "data" / "lokay.fala-package.toml"
    cwd_manifest = tmp_path / "checkout" / "fala" / "lokay.fala-package.toml"
    packaged.parent.mkdir(parents=True)
    cwd_manifest.parent.mkdir(parents=True)
    packaged.write_text('[[correlation_paths]]\nid = "installed"\n', encoding="utf-8")
    cwd_manifest.write_text('[[correlation_paths]]\nid = "upgrading"\n', encoding="utf-8")
    monkeypatch.setattr(preflight, "__file__", str(installed / "preflight.py"))
    monkeypatch.chdir(cwd_manifest.parents[1])
    monkeypatch.delenv("LOKAY_FALA_PACKAGE", raising=False)

    assert preflight.trusted_fala_manifest() == packaged


def test_checkout_accepts_packaged_manifest_override(tmp_path, monkeypatch):
    installed = tmp_path / "checkout" / "src" / "lokay"
    packaged = installed / "data" / "lokay.fala-package.toml"
    source = tmp_path / "checkout" / "fala" / "lokay.fala-package.toml"
    packaged.parent.mkdir(parents=True)
    source.parent.mkdir(parents=True)
    content = '[[correlation_paths]]\nid = "factory_pass"\n'
    packaged.write_text(content, encoding="utf-8")
    source.write_text(content, encoding="utf-8")
    monkeypatch.setattr(preflight, "__file__", str(installed / "preflight.py"))
    monkeypatch.setenv("LOKAY_FALA_PACKAGE", str(packaged))

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


def test_only_lock_owning_daemon_preflight_issues_lease(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("LOKAY_LOG_DIR", str(tmp_path / "runtime" / "logs"))
    monkeypatch.setenv("HOME", str(tmp_path))
    _host_ok(monkeypatch)
    assert preflight.acquire_run_lock(tmp_path / "runtime" / "state" / "mill.lock")
    issued = []
    monkeypatch.setattr(preflight, "issue_health_lease", lambda **kwargs: issued.append(True))

    assert preflight.run_preflight(str(cfg), issue_lease=True)["ok"] is True
    assert issued == [True]


def test_direct_preflight_does_not_issue_lease(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("LOKAY_LOG_DIR", str(tmp_path / "runtime" / "logs"))
    monkeypatch.setenv("HOME", str(tmp_path))
    _host_ok(monkeypatch)
    assert preflight.acquire_run_lock(tmp_path / "runtime" / "state" / "mill.lock")
    issued = []
    monkeypatch.setattr(preflight, "issue_health_lease", lambda **kwargs: issued.append(True))

    assert preflight.run_preflight(str(cfg))["ok"] is True
    assert issued == []


def test_unhealthy_preflight_does_not_issue_lease(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("LOKAY_LOG_DIR", str(tmp_path / "runtime" / "logs"))
    _host_ok(monkeypatch)
    monkeypatch.setattr(
        preflight.shutil,
        "which",
        lambda command, **kwargs: None if command == "omp" else f"/usr/bin/{command}",
    )
    issued = []
    monkeypatch.setattr(preflight, "issue_health_lease", lambda **kwargs: issued.append(True))

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
    monkeypatch.setattr(preflight, "issue_health_lease", lambda **kwargs: issued.append(True))
    result = preflight.run_preflight(str(cfg))
    assert result["carrier_ok"] is False
    assert issued == []
    assert next(x for x in result["findings"] if x["name"] == "fala_manifest_provenance")["ok"] is False

def test_github_auth_skips_user_when_leftover_probe_already_proved(monkeypatch):
    """Leftover-probe host skips GitHub /user this tick. Hosted ticks without leftover lists still probe."""
    from lokay import preflight_checks

    monkeypatch.setenv("LOKAY_LEFTOVER_PROBE_GH_OK", "1")

    def fake_run(argv, **kwargs):
        raise AssertionError(f"must not probe GitHub /user: {argv}")

    monkeypatch.setattr(preflight_checks.shutil, "which", lambda command, **kwargs: "/usr/bin/gh")
    monkeypatch.setattr(preflight_checks.subprocess, "run", fake_run)
    out = preflight_checks.check_github_authentication()
    assert out["ok"] is True
    assert out["code"] == "ok"


def test_github_auth_treats_user_503_as_ok_when_token_present(monkeypatch):
    """Mini froze closeout while /user was 503 and gh auth status was fine."""
    from lokay import preflight_checks

    calls: list[tuple[str, ...]] = []

    def fake_run(argv, **kwargs):
        cmd = tuple(argv)
        calls.append(cmd)
        if cmd[:3] == ("gh", "api", "user"):
            return type(
                "C",
                (),
                {
                    "returncode": 1,
                    "stdout": "",
                    "stderr": (
                        "gh: No server is currently available to service "
                        "your request. (HTTP 503)"
                    ),
                },
            )()
        if cmd[:3] == ("gh", "auth", "status"):
            return type("C", (), {"returncode": 0, "stdout": "Logged in", "stderr": ""})()
        raise AssertionError(argv)

    monkeypatch.setattr(preflight_checks.shutil, "which", lambda command, **kwargs: "/usr/bin/gh")
    monkeypatch.setattr(preflight_checks.subprocess, "run", fake_run)
    out = preflight_checks.check_github_authentication()
    assert out["ok"] is True
    assert out["code"] == "ok"
    assert ("gh", "auth", "status", "--hostname", "github.com") in calls


def test_github_auth_stays_unavailable_on_401(monkeypatch):
    from lokay import preflight_checks

    def fake_run(argv, **kwargs):
        cmd = tuple(argv)
        if cmd[:3] == ("gh", "api", "user"):
            return type(
                "C",
                (),
                {"returncode": 1, "stdout": "", "stderr": "HTTP 401: Bad credentials"},
            )()
        raise AssertionError(f"must not fall back on 401: {argv}")

    monkeypatch.setattr(preflight_checks.shutil, "which", lambda command, **kwargs: "/usr/bin/gh")
    monkeypatch.setattr(preflight_checks.subprocess, "run", fake_run)
    out = preflight_checks.check_github_authentication()
    assert out["ok"] is False
    assert out["code"] == "unavailable"


def test_preflight_releases_gate_when_user_api_is_503(tmp_path, monkeypatch):
    from lokay import preflight_checks

    cfg = _config(tmp_path)
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("LOKAY_LOG_DIR", str(tmp_path / "runtime" / "logs"))
    ok = type("C", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    monkeypatch.setattr(preflight.shutil, "which", lambda command, **kwargs: f"/usr/bin/{command}")
    monkeypatch.setattr(preflight.subprocess, "run", lambda *a, **k: ok)

    def fake_run(argv, **kwargs):
        cmd = tuple(argv)
        if cmd[:3] == ("gh", "api", "user"):
            return type(
                "C",
                (),
                {
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "HTTP 503\nNo server is currently available",
                },
            )()
        if cmd[:2] == ("gh", "auth"):
            return ok
        raise AssertionError(argv)

    monkeypatch.setattr(
        preflight_checks.shutil,
        "which",
        lambda command, **kwargs: "/usr/bin/gh" if command == "gh" else "/usr/bin/omp",
    )
    monkeypatch.setattr(preflight_checks.subprocess, "run", fake_run)
    result = preflight.run_preflight(str(cfg))
    assert result["ok"] is True, result
    finding = next(x for x in result["findings"] if x["name"] == "github_authentication")
    assert finding["ok"] is True


def test_healthy_preflight_does_not_rerun_host_checks(tmp_path, monkeypatch):
    """Idle mill already passed host checks; a second _check only re-hits GitHub."""
    cfg = _config(tmp_path)
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("LOKAY_LOG_DIR", str(tmp_path / "runtime" / "logs"))
    (tmp_path / "runtime" / "logs").mkdir(parents=True)
    (tmp_path / "runtime" / "state").mkdir(parents=True)
    (tmp_path / "runtime" / "worktrees").mkdir(parents=True)
    _host_ok(monkeypatch)
    calls = {"n": 0}
    real = preflight._check

    def counted(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(preflight, "_check", counted)
    result = preflight.run_preflight(str(cfg))
    assert result["ok"] is True, result
    assert calls["n"] == 1


def test_unhealthy_preflight_still_reruns_host_checks(tmp_path, monkeypatch):
    """Repair still needs a second _check so locale / PATH / dirs take effect."""
    cfg = _config(tmp_path)
    monkeypatch.delenv("LANG", raising=False)
    monkeypatch.setenv("LOKAY_LOG_DIR", str(tmp_path / "runtime" / "logs"))
    _host_ok(monkeypatch)
    calls = {"n": 0}
    real = preflight._check

    def counted(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(preflight, "_check", counted)
    result = preflight.run_preflight(str(cfg))
    assert result["ok"] is True, result
    assert calls["n"] == 2

