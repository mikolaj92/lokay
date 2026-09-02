"""Detached issue-to-PR activation barrier and Fala entry contract."""

from __future__ import annotations
import os
from types import SimpleNamespace
import lokay.compose.issue_to_pr as issue_to_pr
from lokay.compose.issue_to_pr import _await_detach_activation


def test_activation_pipe_releases_child_only_on_parent_token(monkeypatch):
    read_fd, write_fd = os.pipe()
    try:
        monkeypatch.setenv("LOKAY_ISSUE_TO_PR_ACTIVATION_FD", str(read_fd))
        os.write(write_fd, b"1")
        assert _await_detach_activation() is True
    finally:
        os.close(write_fd)


def test_activation_pipe_eof_refuses_unpublished_child(monkeypatch):
    read_fd, write_fd = os.pipe()
    try:
        monkeypatch.setenv("LOKAY_ISSUE_TO_PR_ACTIVATION_FD", str(read_fd))
        os.close(write_fd)
        write_fd = -1
        assert _await_detach_activation() is False
    finally:
        if write_fd >= 0:
            os.close(write_fd)


def test_no_activation_fd_preserves_direct_entry(monkeypatch):
    monkeypatch.delenv("LOKAY_ISSUE_TO_PR_ACTIVATION_FD", raising=False)
    assert _await_detach_activation() is True


def test_composer_delegates_closed_and_delivery_decisions_to_fala(tmp_path, monkeypatch):
    from lokay.preflight import acquire_run_lock, issue_health_lease

    monkeypatch.setenv("HOME", str(tmp_path))
    lock = tmp_path / ".lokay" / "mill.lock"
    assert acquire_run_lock(lock)
    issue_health_lease(lock_path=lock)
    monkeypatch.delenv("LOKAY_ISSUE_TO_PR_ACTIVATION_FD", raising=False)
    calls = []
    monkeypatch.setattr(
        issue_to_pr,
        "load_config",
        lambda _p: SimpleNamespace(mode="live", state_path="state"),
    )
    monkeypatch.setattr(issue_to_pr, "append_event", lambda *_: None)
    monkeypatch.setattr(
        issue_to_pr,
        "run_path",
        lambda **kw: calls.append(kw)
        or {"ok": True, "reason": "issue_closed", "stopped": True},
    )
    out = issue_to_pr.compose_issue_to_pr(
        config_path=None, repo="owner/repo", issue_number=7, live=True
    )
    assert calls[0]["path_id"] == "issue_to_pr" and out["reason"] == "issue_closed"


def test_live_requires_live_config(monkeypatch):
    monkeypatch.delenv("LOKAY_ISSUE_TO_PR_ACTIVATION_FD", raising=False)
    monkeypatch.setattr(
        issue_to_pr, "load_config", lambda _p: SimpleNamespace(mode="observe")
    )
    out = issue_to_pr.compose_issue_to_pr(
        config_path=None, repo="owner/repo", issue_number=7, live=True
    )
    assert out["ok"] is False
