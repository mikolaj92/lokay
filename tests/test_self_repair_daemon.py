from lokay.proc import daemon


def _write_cfg(tmp_path, *, state_name: str = "state.jsonl") -> str:
    cfg = tmp_path / "config.yaml"
    state_dir = tmp_path / "lokay-state"
    state_dir.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        f"""
mode: dry-run
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: false
  command: true
  args: ["{{prompt}}"]
state:
  path: {state_dir / state_name}
""",
        encoding="utf-8",
    )
    return str(cfg)


def test_daemon_selects_unique_health_lease_path(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(daemon, "acquire_run_lock", lambda p: False)
    cfg = _write_cfg(tmp_path)

    assert daemon.main(["--config", cfg, "--outbox", str(tmp_path / "out")]) == 1

    path = __import__("os").environ["LOKAY_HEALTH_LEASE_PATH"]
    assert path.startswith(str((tmp_path / "lokay-state").resolve()))
    assert "health-lease-" in path


def test_daemon_lock_uses_state_parent_not_home_default(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    seen = {}

    def capture(path):
        seen["lock"] = path
        return False

    monkeypatch.setattr(daemon, "acquire_run_lock", capture)
    cfg = _write_cfg(tmp_path)
    assert daemon.main(["--config", cfg, "--outbox", str(tmp_path / "out")]) == 1
    assert seen["lock"] == (tmp_path / "lokay-state" / "mill.lock").resolve()


def test_daemon_lock_overlap_is_not_recorded_as_preflight_failure(monkeypatch, tmp_path, capsys):
    outbox = tmp_path / "outbox.jsonl"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(daemon, "acquire_run_lock", lambda p: False)
    cfg = _write_cfg(tmp_path)

    assert daemon.main(["--config", cfg, "--outbox", str(outbox)]) == 1

    assert not outbox.exists()
    payload = capsys.readouterr().out
    assert '"health": "overlap"' in payload
    assert '"code": "overlap"' in payload


def test_healthy_daemon_reuses_preflight_lease_for_product(monkeypatch, tmp_path):
    health = {"ok": True, "carrier_ok": True, "fingerprint": "healthy"}
    captured = []
    cfg = _write_cfg(tmp_path)
    monkeypatch.setattr(daemon, "acquire_run_lock", lambda p: True)
    monkeypatch.setattr(daemon, "run_preflight", lambda *a, **k: health)
    monkeypatch.setattr(daemon, "compose_daemon_cycle", lambda **kwargs: captured.append(kwargs) or {"ok": True})

    assert daemon.main(["--config", cfg, "--outbox", str(tmp_path / "out")]) == 0
    assert captured == [{"config_path": cfg, "max_passes": 8}]


def test_healthy_daemon_delegates_recovery_order_to_fala_cycle(monkeypatch, tmp_path):
    cfg = _write_cfg(tmp_path)
    monkeypatch.setattr(daemon, "acquire_run_lock", lambda p: True)
    monkeypatch.setattr(daemon, "run_preflight", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(
        daemon,
        "run_self_repair",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("daemon orchestrated repair")),
    )
    monkeypatch.setattr(
        daemon,
        "compose_daemon_cycle",
        lambda **k: {"ok": False, "health": "self_repair_restart_required"},
    )
    assert daemon.main(["--config", cfg, "--outbox", str(tmp_path / "out")]) == 1


def test_preflight_singleton_overlap_never_enters_self_repair(monkeypatch, tmp_path, capsys):
    cfg = _write_cfg(tmp_path)
    monkeypatch.setattr(daemon, "acquire_run_lock", lambda p: True)
    monkeypatch.setattr(
        daemon,
        "run_preflight",
        lambda *a, **k: {
            "ok": False,
            "carrier_ok": False,
            "health": "overlap",
            "operational_overlap": True,
        },
    )
    monkeypatch.setattr(
        daemon,
        "run_self_repair",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("repair ran")),
    )
    monkeypatch.setattr(
        daemon,
        "compose_daemon_cycle",
        lambda **k: (_ for _ in ()).throw(AssertionError("product ran")),
    )

    assert daemon.main(["--config", cfg, "--outbox", str(tmp_path / "out")]) == 1
    assert '"health": "overlap"' in capsys.readouterr().out


def test_unhealthy_daemon_services_lane_and_never_product(monkeypatch, tmp_path, capsys):
    cfg = _write_cfg(tmp_path)
    monkeypatch.setattr(daemon, "acquire_run_lock", lambda p: True)
    monkeypatch.setattr(daemon, "run_preflight", lambda *a, **k: {"ok": False, "carrier_ok": True, "incident_url": "https://github.com/mikolaj92/lokay/issues/4"})
    monkeypatch.setattr(daemon, "run_self_repair", lambda *a, **k: {"ok": False})
    monkeypatch.setattr(daemon, "compose_daemon_cycle", lambda **k: (_ for _ in ()).throw(AssertionError("product ran")))
    assert daemon.main(["--config", cfg, "--outbox", str(tmp_path / "out")]) == 1


def test_validated_repair_requires_restart_not_product(monkeypatch, tmp_path, capsys):
    cfg = _write_cfg(tmp_path)
    monkeypatch.setattr(daemon, "acquire_run_lock", lambda p: True)
    monkeypatch.setattr(daemon, "run_preflight", lambda *a, **k: {"ok": False, "carrier_ok": True})
    monkeypatch.setattr(daemon, "run_self_repair", lambda *a, **k: {"ok": True, "validated": True})
    monkeypatch.setattr(daemon, "compose_daemon_cycle", lambda **k: (_ for _ in ()).throw(AssertionError("stale product ran")))
    assert daemon.main(["--config", cfg, "--outbox", str(tmp_path / "out")]) == 1
    assert "self_repair_restart_required" in capsys.readouterr().out


def test_carrier_failure_runs_neither_agent_lane_nor_product(monkeypatch, tmp_path):
    cfg = _write_cfg(tmp_path)
    monkeypatch.setattr(daemon, "acquire_run_lock", lambda p: True)
    monkeypatch.setattr(daemon, "run_preflight", lambda *a, **k: {"ok": False, "carrier_ok": False})
    monkeypatch.setattr(daemon, "run_self_repair", lambda *a, **k: (_ for _ in ()).throw(AssertionError("repair ran")))
    monkeypatch.setattr(daemon, "compose_daemon_cycle", lambda **k: (_ for _ in ()).throw(AssertionError("product ran")))
    assert daemon.main(["--config", cfg, "--outbox", str(tmp_path / "out")]) == 1
