"""lokay#1094: harvest_factory_children resolves stuck ledger without upstream."""

from __future__ import annotations

from pathlib import Path

from lokay.proc import harvest_factory_children as harvest_mod


def test_resolve_harvest_args_fills_stuck_path_from_state(tmp_path, monkeypatch):
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    stuck = tmp_path / "stuck.json"
    stuck.write_text('{"issues": {"mikolaj92/x#1": {"blocked": false}}}', encoding="utf-8")

    class _Cfg:
        config_path = None
        state_path = state

        def active_repos(self):
            return []

    monkeypatch.setattr(
        "lokay.proc._common.load_cfg",
        lambda _ns: _Cfg(),
    )
    monkeypatch.setattr(
        "lokay.stuck.stuck_path_for",
        lambda _state: stuck,
    )

    out = harvest_mod.resolve_harvest_args(
        {"state_path": None, "config_path": None, "live": True},
        {"config_path": None, "repos": []},
        {},
    )
    assert out["ledger"]["stuck_path"] == str(stuck)
    assert "mikolaj92/x#1" in out["ledger"]["stuck"]["issues"]
    assert out["config"]["state_path"] == str(state)
    assert out["config"]["live"] is True


def test_resolve_keeps_explicit_ledger(tmp_path):
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    ledger = {"stuck_path": str(tmp_path / "custom-stuck.json"), "stuck": {"issues": {}}}
    out = harvest_mod.resolve_harvest_args(
        {"state_path": str(state), "live": False},
        {"repos": ["mikolaj92/lokay"]},
        ledger,
    )
    assert out["ledger"]["stuck_path"] == ledger["stuck_path"]
    assert out["scope"]["repos"] == ["mikolaj92/lokay"]
    assert out["config"]["live"] is False
