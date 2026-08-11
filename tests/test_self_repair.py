from pathlib import Path
from types import SimpleNamespace

from lokay import self_repair


def cfg(tmp_path, **kw):
    base = dict(
        state_path=tmp_path / "state.jsonl",
        executor_enabled=True,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def unhealthy(url="https://github.com/mikolaj92/lokay/issues/44"):
    return {
        "ok": False,
        "carrier_ok": True,
        "integrity_ok": False,
        "fingerprint": "abc",
        "incident_url": url,
        "findings": [{"name": "fala_smoke", "ok": False}],
    }


def setup_lane(monkeypatch, tmp_path, **cfg_kw):
    monkeypatch.setattr(self_repair, "load_config", lambda p: cfg(tmp_path, **cfg_kw))
    monkeypatch.setattr(self_repair, "trusted_fala_manifest", lambda: tmp_path / "trusted.toml")


def test_missing_deduplicated_incident_never_runs_fala(monkeypatch, tmp_path):
    setup_lane(monkeypatch, tmp_path)
    monkeypatch.setattr(self_repair, "run_path", lambda **k: (_ for _ in ()).throw(AssertionError()))
    result = self_repair.run_self_repair("x", unhealthy(url=None))
    assert not result["ok"] and result["reason"] == "deduplicated_incident_unavailable"


def test_bootstrap_dependency_failure_avoids_recursion(monkeypatch, tmp_path):
    setup_lane(monkeypatch, tmp_path)
    value = unhealthy()
    value["findings"] = [{"name": "executor_availability", "ok": False}]
    monkeypatch.setattr(self_repair, "run_path", lambda **k: (_ for _ in ()).throw(AssertionError()))
    result = self_repair.run_self_repair("x", value)
    assert result["reason"] == "bootstrap_dependency_unavailable"


def test_carrier_unhealthy_never_runs_fala(monkeypatch, tmp_path):
    setup_lane(monkeypatch, tmp_path)
    value = unhealthy()
    value["carrier_ok"] = False
    monkeypatch.setattr(self_repair, "run_path", lambda **k: (_ for _ in ()).throw(AssertionError()))
    result = self_repair.run_self_repair("x", value)
    assert result["reason"] == "carrier_unhealthy"


def test_self_repair_is_one_fala_path_and_returns_restart(monkeypatch, tmp_path):
    setup_lane(monkeypatch, tmp_path)
    calls = []

    def fake_path(**kwargs):
        calls.append(kwargs)
        return {
            "ok": True,
            "validated": True,
            "restart_required": True,
            "commit": "deadbeef",
            "incident_closed": True,
            "gate_released": False,
        }

    monkeypatch.setattr(self_repair, "run_path", fake_path)
    result = self_repair.run_self_repair("x", unhealthy())

    assert result["ok"] and result["health"] == "restart_required"
    assert result["commit"] == "deadbeef" and not result["gate_released"]
    assert len(calls) == 1
    call = calls[0]
    assert call["path_id"] == "self_repair"
    assert call["repo"] == "mikolaj92/lokay"
    assert call["issue"] == 44 and call["live"] is True
    assert call["extra_inputs"]["fingerprint"] == "abc"


def test_fala_failure_stays_closed(monkeypatch, tmp_path):
    setup_lane(monkeypatch, tmp_path)
    monkeypatch.setattr(self_repair, "run_path", lambda **k: {"ok": False, "error": "push rejected"})
    result = self_repair.run_self_repair("x", unhealthy())
    assert not result["ok"]
    assert result["health"] == "self_repair_failed"
    assert result["reason"] == "fala_self_repair_failed"
