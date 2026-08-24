"""Production tick and factory-pass use one authored Fala graph."""

import inspect
from lokay.compose import factory as factory_mod
from lokay.proc import factory_tick


def _fala_ok(**kwargs):
    return {"ok": True, "health": "idle", "path_id": kwargs.get("path_id")}


def test_factory_pass_live_invokes_authored_path(monkeypatch):
    called = {}
    monkeypatch.delenv("LOKAY_OFFLINE", raising=False)
    monkeypatch.setattr(
        factory_mod,
        "run_path",
        lambda **kwargs: called.update(kwargs) or _fala_ok(**kwargs),
    )
    out = factory_mod.compose_factory_pass(
        config_path="config.yaml", live=True, db_path="/tmp/factory"
    )
    assert (
        called["path_id"] == "factory_pass"
        and called["live"] is True
        and out["engine"] == "fala"
    )


def test_factory_pass_dry_run_invokes_authored_path(monkeypatch):
    called = {}
    monkeypatch.delenv("LOKAY_OFFLINE", raising=False)
    monkeypatch.setattr(
        factory_mod,
        "run_path",
        lambda **kwargs: called.update(kwargs) or _fala_ok(**kwargs),
    )
    out = factory_mod.compose_factory_pass(config_path="config.yaml", live=False)
    assert called["path_id"] == "factory_pass" and out["planned"] is True


def test_factory_tick_live_invokes_factory_pass(monkeypatch, capsys):
    called = {}
    monkeypatch.delenv("LOKAY_OFFLINE", raising=False)
    monkeypatch.setattr(
        factory_mod,
        "run_path",
        lambda **kwargs: called.update(kwargs) or _fala_ok(**kwargs),
    )
    assert factory_tick.main(["--live", "--config", "config.yaml"]) == 0
    capsys.readouterr()
    assert called["path_id"] == "factory_pass"


def test_live_offline_fails_closed(monkeypatch):
    monkeypatch.setenv("LOKAY_OFFLINE", "1")
    monkeypatch.setattr(
        factory_mod, "run_path", lambda **_: (_ for _ in ()).throw(AssertionError())
    )
    out = factory_mod.compose_factory_pass(config_path="config.yaml", live=True)
    assert out["ok"] is False and out["engine"] == "fala"


def test_offline_dry_run_is_closed_non_graph_result(monkeypatch):
    monkeypatch.setenv("LOKAY_OFFLINE", "1")
    monkeypatch.setattr(
        factory_mod, "run_path", lambda **_: (_ for _ in ()).throw(AssertionError())
    )
    out = factory_mod.compose_factory_pass(config_path="config.yaml", live=False)
    assert out["ok"] and out["health"] == "offline" and out["engine"] == "fala"


def test_factory_tick_module_has_no_compose_tick_import():
    src = inspect.getsource(factory_tick)
    assert (
        "from lokay.compose.factory import compose_factory_pass" in src
        and "compose.tick" not in src
    )
