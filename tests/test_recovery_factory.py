import json

from lokay.proc import recovery_factory


def test_recovery_factory_emits_compact_verdict_not_factory_journal(monkeypatch, capsys):
    bulky = {"ok": True, "health": "idle", "db": "/tmp/factory.sqlite", "run_id": "run-1",
             "fala": {"effector_results": {"large": "x" * 100_000}},
             "terminal": {"payload": "x" * 100_000}, "steps": ["x" * 100_000]}
    monkeypatch.setattr(recovery_factory, "compose_factory_pass", lambda **_: bulky)

    assert recovery_factory.main(["--config", "config.yaml"]) == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope == {"ok": True, "factory": {
        "ok": True, "health": "idle", "db": "/tmp/factory.sqlite", "run_id": "run-1"
    }}
    assert len(json.dumps(envelope)) < 256
