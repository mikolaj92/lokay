"""Pass ceiling must match LaunchAgent / lokay-service.sh (default 2400)."""

from lokay.compose.daemon_cycle import (
    DEFAULT_PASS_CEILING_SECONDS,
    resolve_pass_ceiling_seconds,
)


def test_default_ceiling_is_2400_not_180():
    assert DEFAULT_PASS_CEILING_SECONDS == 2400.0
    assert resolve_pass_ceiling_seconds(None, env={}) == 2400.0
    assert resolve_pass_ceiling_seconds(None, env={"LOKAY_PASS_CEILING_SECONDS": ""}) == 2400.0


def test_env_ceiling_wins_when_explicit_absent():
    assert resolve_pass_ceiling_seconds(None, env={"LOKAY_PASS_CEILING_SECONDS": "2400"}) == 2400.0
    assert resolve_pass_ceiling_seconds(None, env={"LOKAY_PASS_CEILING_SECONDS": "90"}) == 90.0


def test_explicit_ceiling_wins_over_env():
    assert (
        resolve_pass_ceiling_seconds(0.02, env={"LOKAY_PASS_CEILING_SECONDS": "2400"})
        == 0.02
    )


def test_invalid_env_falls_back_to_2400():
    assert resolve_pass_ceiling_seconds(None, env={"LOKAY_PASS_CEILING_SECONDS": "nope"}) == 2400.0
    assert resolve_pass_ceiling_seconds(None, env={"LOKAY_PASS_CEILING_SECONDS": "0"}) == 2400.0


def test_run_daemon_product_cycle_passes_resolved_ceiling(monkeypatch):
    from lokay.proc import run_daemon_product_cycle as mod

    seen = {}

    def fake_compose(*, config_path, max_passes, pass_ceiling_seconds):
        seen["config_path"] = config_path
        seen["max_passes"] = max_passes
        seen["pass_ceiling_seconds"] = pass_ceiling_seconds
        return {"ok": True, "health": "idle"}

    monkeypatch.setattr(mod, "compose_daemon_cycle", fake_compose)
    monkeypatch.setenv("LOKAY_PASS_CEILING_SECONDS", "2400")
    out = mod.run(config_path="/tmp/c.yaml", max_passes=3)
    assert out["ok"] is True
    assert seen["pass_ceiling_seconds"] == 2400.0
    assert seen["max_passes"] == 3


def test_compose_default_no_longer_silent_180():
    import inspect
    from lokay.compose import daemon_cycle

    src = inspect.getsource(daemon_cycle.compose_daemon_cycle)
    assert "180" not in src or "pass_ceiling_seconds: float = 180" not in src
    assert "resolve_pass_ceiling_seconds" in src
