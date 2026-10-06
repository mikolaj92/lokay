import os
from types import SimpleNamespace

from lokay import preflight


def test_standalone_gate_issues_valid_capability_under_its_checked_lock(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LOKAY_HEALTH_LEASE", raising=False)
    monkeypatch.delenv("LOKAY_HEALTH_LEASE_PATH", raising=False)
    monkeypatch.delenv("LOKAY_DISABLE_HEALTH_LEASE_ISSUE", raising=False)
    lock = tmp_path / "configured-state" / "lokay.lock"
    lock.parent.mkdir()
    cfg = SimpleNamespace(state_path=lock.parent / "state.jsonl", worktrees_root=tmp_path / "worktrees",
                          live=False, executor_enabled=False)

    def healthy_check(*args, **kwargs):
        assert preflight.acquire_run_lock(lock)
        return {"ok": True, "findings": []}, cfg

    monkeypatch.setattr(preflight, "_check", healthy_check)
    monkeypatch.setattr(preflight, "_close_resolved_incidents", lambda *args: {})
    monkeypatch.setattr(preflight, "_incident_repo", lambda cfg: "offline/canary")
    try:
        preflight.require_healthy("offline.yaml")
        assert preflight.health_lease_status(lock_path=lock) == (True, "ok")
        assert len(os.environ["LOKAY_HEALTH_LEASE"]) == 64
    finally:
        preflight.revoke_health_lease()
