"""lokay#1063: live factory_pass must harvest before parent Fala runs."""

from __future__ import annotations

from lokay.compose import factory as factory_mod


def test_live_factory_pass_harvests_before_run_path(monkeypatch):
    calls: list[tuple[str | None, bool]] = []

    def fake_harvest(*, config_path, live):
        calls.append((config_path, live))

    monkeypatch.setattr(
        "lokay.child_harvest.harvest_idle_lokay_stuck", fake_harvest
    )
    monkeypatch.setattr(factory_mod, "_offline", lambda: False)
    monkeypatch.setattr(
        factory_mod,
        "run_path",
        lambda **kwargs: {"ok": True, "path_id": kwargs.get("path_id")},
    )
    monkeypatch.setattr(
        factory_mod, "wrapper_journal_dir", lambda _name: "/tmp/lokay-test-journal"
    )

    out = factory_mod.compose_factory_pass(config_path="config.yaml", live=True)
    assert out.get("ok") is True
    assert calls == [("config.yaml", True)]


def test_dry_factory_pass_skips_harvest(monkeypatch):
    calls: list[object] = []

    def fake_harvest(**_kwargs):
        calls.append(True)

    monkeypatch.setattr(
        "lokay.child_harvest.harvest_idle_lokay_stuck", fake_harvest
    )
    monkeypatch.setattr(factory_mod, "_offline", lambda: False)
    monkeypatch.setattr(
        factory_mod,
        "run_path",
        lambda **kwargs: {"ok": True, "path_id": kwargs.get("path_id")},
    )
    monkeypatch.setattr(
        factory_mod, "wrapper_journal_dir", lambda _name: "/tmp/lokay-test-journal"
    )

    out = factory_mod.compose_factory_pass(config_path="config.yaml", live=False)
    assert out.get("ok") is True
    assert calls == []
