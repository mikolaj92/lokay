from lokay.proc import daemon


def test_daemon_selects_unique_health_lease_path(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(daemon, "acquire_run_lock", lambda p: False)

    assert daemon.main(["--config", "x", "--outbox", str(tmp_path / "out")]) == 1

    path = __import__("os").environ["LOKAY_HEALTH_LEASE_PATH"]
    assert path.startswith(str(tmp_path / ".lokay" / "health-lease-"))
    assert path != str(tmp_path / ".lokay" / "health-lease")


def test_healthy_daemon_reuses_preflight_lease_for_product(monkeypatch, tmp_path):
    health = {"ok": True, "carrier_ok": True, "fingerprint": "healthy"}
    captured = []
    monkeypatch.setattr(daemon, "acquire_run_lock", lambda p: True)
    monkeypatch.setattr(daemon, "run_preflight", lambda *a, **k: health)
    monkeypatch.setattr(daemon, "compose_mill", lambda **kwargs: captured.append(kwargs) or {"ok": True})

    assert daemon.main(["--config", "x", "--outbox", str(tmp_path / "out")]) == 0
    assert captured == [{"config_path": "x", "live": True, "max_passes": 8, "preflight": health}]


def test_preflight_singleton_overlap_never_enters_self_repair(monkeypatch, tmp_path, capsys):
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
        "compose_mill",
        lambda **k: (_ for _ in ()).throw(AssertionError("product ran")),
    )

    assert daemon.main(["--config", "x", "--outbox", str(tmp_path / "out")]) == 1
    assert '"health": "overlap"' in capsys.readouterr().out


def test_unhealthy_daemon_services_lane_and_never_product(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(daemon, "acquire_run_lock", lambda p: True)
    monkeypatch.setattr(daemon, "run_preflight", lambda *a, **k: {"ok": False, "carrier_ok": True, "incident_url": "https://github.com/mikolaj92/lokay/issues/4"})
    monkeypatch.setattr(daemon, "run_self_repair", lambda *a, **k: {"ok": False})
    monkeypatch.setattr(daemon, "compose_mill", lambda **k: (_ for _ in ()).throw(AssertionError("product ran")))
    assert daemon.main(["--config", "x", "--outbox", str(tmp_path / "out")]) == 1


def test_validated_repair_requires_restart_not_product(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(daemon, "acquire_run_lock", lambda p: True)
    monkeypatch.setattr(daemon, "run_preflight", lambda *a, **k: {"ok": False, "carrier_ok": True})
    monkeypatch.setattr(daemon, "run_self_repair", lambda *a, **k: {"ok": True, "validated": True})
    monkeypatch.setattr(daemon, "compose_mill", lambda **k: (_ for _ in ()).throw(AssertionError("stale product ran")))
    assert daemon.main(["--config", "x", "--outbox", str(tmp_path / "out")]) == 1
    assert "self_repair_restart_required" in capsys.readouterr().out


def test_carrier_failure_runs_neither_agent_lane_nor_product(monkeypatch, tmp_path):
    monkeypatch.setattr(daemon, "acquire_run_lock", lambda p: True)
    monkeypatch.setattr(daemon, "run_preflight", lambda *a, **k: {"ok": False, "carrier_ok": False})
    monkeypatch.setattr(daemon, "run_self_repair", lambda *a, **k: (_ for _ in ()).throw(AssertionError("repair ran")))
    monkeypatch.setattr(daemon, "compose_mill", lambda **k: (_ for _ in ()).throw(AssertionError("product ran")))
    assert daemon.main(["--config", "x", "--outbox", str(tmp_path / "out")]) == 1
