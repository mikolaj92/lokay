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
    assert seen["lock"] == (tmp_path / "lokay-state" / "lokay.lock").resolve()


def test_daemon_lock_overlap_is_not_recorded_as_preflight_failure(
    monkeypatch, tmp_path, capsys
):
    outbox = tmp_path / "outbox.jsonl"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(daemon, "acquire_run_lock", lambda p: False)
    cfg = _write_cfg(tmp_path)

    assert daemon.main(["--config", cfg, "--outbox", str(outbox)]) == 1

    assert not outbox.exists()
    payload = capsys.readouterr().out
    assert '"health": "overlap"' in payload
    assert '"code": "overlap"' in payload


def test_daemon_passes_closed_preflight_to_authored_entry(monkeypatch, tmp_path):
    cfg = _write_cfg(tmp_path)
    health = {"ok": True, "carrier_ok": True}
    seen = []
    monkeypatch.setattr(daemon, "acquire_run_lock", lambda p: True)
    monkeypatch.setattr(daemon, "run_preflight", lambda *a, **k: health)
    monkeypatch.setattr(
        "lokay.proc.daemon_entry_subflow.run",
        lambda **k: seen.append(k) or {"ok": True},
    )
    assert daemon.main(["--config", cfg, "--outbox", str(tmp_path / "out")]) == 0
    assert seen == [{"config_path": cfg, "max_passes": 8, "preflight": health}]


def test_daemon_does_not_contain_product_or_repair_routing():
    import inspect

    source = inspect.getsource(daemon.main)
    assert "compose_daemon_cycle" not in source and "run_self_repair" not in source
