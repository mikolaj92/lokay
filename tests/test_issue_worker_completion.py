"""Activated live workers close their delegated record on every Python exit."""
from types import SimpleNamespace

import pytest

from lokay.compose import issue_to_pr


@pytest.mark.parametrize("exit_kind", ["graph_error", "config_error", "wrong_mode", "success"])
def test_activated_worker_completes_lease(monkeypatch, tmp_path, exit_kind):
    from lokay.proc import health_delegation

    completed = []
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "a" * 64)
    monkeypatch.setattr(issue_to_pr, "_await_detach_activation", lambda: True)
    monkeypatch.setattr("lokay.preflight.health_lease_status", lambda: (True, "ok"))
    monkeypatch.setattr(health_delegation, "heartbeat_delegated_lease", lambda: {"ok": True})
    monkeypatch.setattr(health_delegation, "complete_delegated_lease", lambda: completed.append(1) or {"ok": True})
    monkeypatch.setattr(issue_to_pr, "append_event", lambda *args: None)

    def config(_):
        if exit_kind == "config_error":
            raise ValueError("bad config")
        return SimpleNamespace(mode="dry-run" if exit_kind == "wrong_mode" else "live", state_path=tmp_path / "state")

    def graph(**kwargs):
        if exit_kind == "graph_error":
            raise RuntimeError("graph unavailable")
        return {"ok": True}

    monkeypatch.setattr(issue_to_pr, "load_config", config)
    monkeypatch.setattr(issue_to_pr, "run_path", graph)
    if exit_kind in {"graph_error", "config_error"}:
        with pytest.raises((RuntimeError, ValueError)):
            issue_to_pr.compose_issue_to_pr(config_path=None, repo="o/r", issue_number=1, live=True)
    else:
        out = issue_to_pr.compose_issue_to_pr(config_path=None, repo="o/r", issue_number=1, live=True)
        assert out["ok"] is (exit_kind == "success")
    assert completed == [1]


@pytest.mark.parametrize("raises", [False, True])
def test_lease_completion_failure_is_visible(monkeypatch, raises):
    from lokay.proc import health_delegation

    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "a" * 64)
    monkeypatch.setattr(issue_to_pr, "_await_detach_activation", lambda: True)
    monkeypatch.setattr(issue_to_pr, "load_config", lambda _: SimpleNamespace(mode="dry-run"))

    def complete():
        if raises:
            raise OSError("disk full")
        return {"ok": False, "reason": "token_mismatch"}

    monkeypatch.setattr(health_delegation, "complete_delegated_lease", complete)
    with pytest.warns(RuntimeWarning, match="delegated lease completion failed"):
        out = issue_to_pr.compose_issue_to_pr(config_path=None, repo="o/r", issue_number=1, live=True)
    assert out["ok"] is False
