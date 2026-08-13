"""Production factory-tick / factory-pass is one Fala mill — not compose_tick."""

from __future__ import annotations

import inspect

from lokay.compose import factory as factory_mod
from lokay.proc import factory_tick


def _fala_ok(**kwargs):
    return {"ok": True, "health": "idle", "path_id": kwargs.get("path_id")}


def test_factory_pass_live_invokes_fala_not_tick(monkeypatch):
    called: dict = {}

    def fake_run_path(**kwargs):
        called.update(kwargs)
        return _fala_ok(**kwargs)

    def boom(**_kwargs):
        raise AssertionError("compose_tick must not run for a live mill")

    monkeypatch.delenv("LOKAY_OFFLINE", raising=False)
    monkeypatch.setattr(factory_mod, "run_path", fake_run_path)
    monkeypatch.setattr(factory_mod, "compose_tick", boom)

    out = factory_mod.compose_factory_pass(
        config_path="config.yaml", live=True, db_path="/tmp/lokay-factory-test"
    )

    assert called["path_id"] == "factory_pass"
    assert called["live"] is True
    assert out["ok"] is True
    assert out["engine"] == "fala"
    assert out["kind"] == "factory_pass"


def test_factory_pass_dry_run_invokes_fala_not_tick(monkeypatch):
    called: dict = {}

    def fake_run_path(**kwargs):
        called.update(kwargs)
        return _fala_ok(**kwargs)

    def boom(**_kwargs):
        raise AssertionError("compose_tick must not run for a Fala dry-run")

    monkeypatch.delenv("LOKAY_OFFLINE", raising=False)
    monkeypatch.setattr(factory_mod, "run_path", fake_run_path)
    monkeypatch.setattr(factory_mod, "compose_tick", boom)

    out = factory_mod.compose_factory_pass(config_path="config.yaml", live=False)

    assert called["path_id"] == "factory_pass"
    assert called["live"] is False
    assert out["engine"] == "fala"
    assert out["planned"] is True


def test_factory_tick_live_invokes_factory_pass_not_tick(monkeypatch, capsys):
    called: dict = {}

    def fake_run_path(**kwargs):
        called.update(kwargs)
        return _fala_ok(**kwargs)

    def boom(**_kwargs):
        raise AssertionError("compose_tick must not run for lokay-factory-tick --live")

    monkeypatch.delenv("LOKAY_OFFLINE", raising=False)
    monkeypatch.setattr(factory_mod, "run_path", fake_run_path)
    monkeypatch.setattr(factory_mod, "compose_tick", boom)

    code = factory_tick.main(["--live", "--config", "config.yaml"])
    capsys.readouterr()

    assert code == 0
    assert called["path_id"] == "factory_pass"
    assert called["live"] is True


def test_live_offline_fail_closed_does_not_call_tick(monkeypatch):
    monkeypatch.setenv("LOKAY_OFFLINE", "1")

    def boom_path(**_kwargs):
        raise AssertionError("live+offline must fail closed before Fala")

    def boom_tick(**_kwargs):
        raise AssertionError("live mill cannot skip Fala via compose_tick")

    monkeypatch.setattr(factory_mod, "run_path", boom_path)
    monkeypatch.setattr(factory_mod, "compose_tick", boom_tick)

    out = factory_mod.compose_factory_pass(config_path="config.yaml", live=True)
    assert out["ok"] is False
    assert "cannot skip Fala" in str(out.get("error") or "")
    assert out.get("engine") == "fala"


def test_offline_dry_run_uses_documented_tick_escape(monkeypatch):
    monkeypatch.setenv("LOKAY_OFFLINE", "1")

    def fake_tick(**kwargs):
        assert kwargs["live"] is False
        return {"ok": True, "health": "offline", "offline": True}

    def boom(**_kwargs):
        raise AssertionError("offline dry-run escape must not host Fala")

    monkeypatch.setattr(factory_mod, "compose_tick", fake_tick)
    monkeypatch.setattr(factory_mod, "run_path", boom)

    out = factory_mod.compose_factory_pass(config_path="config.yaml", live=False)
    assert out["ok"] is True
    assert out["health"] == "offline"


def test_factory_tick_module_does_not_import_compose_tick():
    src = inspect.getsource(factory_tick)
    assert "from lokay.compose.factory import compose_factory_pass" in src
    assert "from lokay.compose.tick import compose_tick" not in src
