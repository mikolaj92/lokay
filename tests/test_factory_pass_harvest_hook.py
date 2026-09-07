"""lokay#1063: live factory_pass must harvest before parent Fala runs."""

from __future__ import annotations

from lokay.compose import factory as factory_mod


def test_live_factory_pass_invokes_run_path_without_python_harvest_hook(monkeypatch):
    run_calls: list[dict] = []

    monkeypatch.setattr(factory_mod, "_offline", lambda: False)
    monkeypatch.setattr(
        factory_mod,
        "run_path",
        lambda **kwargs: run_calls.append(kwargs) or {"ok": True, "path_id": kwargs.get("path_id")},
    )
    monkeypatch.setattr(
        factory_mod, "wrapper_journal_dir", lambda _name: "/tmp/lokay-test-journal"
    )

    out = factory_mod.compose_factory_pass(config_path="config.yaml", live=True)
    assert out.get("ok") is True
    assert len(run_calls) == 1
    assert run_calls[0]["path_id"] == "factory_pass"


def test_dry_factory_pass_runs_path(monkeypatch):
    run_calls: list[dict] = []

    monkeypatch.setattr(factory_mod, "_offline", lambda: False)
    monkeypatch.setattr(
        factory_mod,
        "run_path",
        lambda **kwargs: run_calls.append(kwargs) or {"ok": True, "path_id": kwargs.get("path_id")},
    )
    monkeypatch.setattr(
        factory_mod, "wrapper_journal_dir", lambda _name: "/tmp/lokay-test-journal"
    )

    out = factory_mod.compose_factory_pass(config_path="config.yaml", live=False)
    assert out.get("ok") is True
    assert len(run_calls) == 1
    assert run_calls[0]["path_id"] == "factory_pass"
