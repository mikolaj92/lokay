import os
from lokay import repair_broker


def test_spoofed_old_repair_env_never_authorizes(monkeypatch):
    monkeypatch.delenv("LOKAY_REPAIR_BROKER", raising=False)
    monkeypatch.setenv("LOKAY_SELF_REPAIR_LEASE", "bearer")
    monkeypatch.setenv("LOKAY_SELF_REPAIR_FINGERPRINT", "fp")
    assert repair_broker.broker_authorized() is False


def test_executor_environment_strips_broker_authority():
    from pathlib import Path
    text = (Path(__file__).parents[1] / "src/lokay/agent.py").read_text()
    assert '"LOKAY_REPAIR_BROKER": ""' in text
    assert '"LOKAY_SELF_REPAIR_LEASE"' not in text
