"""Detached issue-to-PR activation barrier."""

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


def test_no_activation_fd_preserves_direct_issue_to_pr_entry(monkeypatch):
    monkeypatch.delenv("LOKAY_ISSUE_TO_PR_ACTIVATION_FD", raising=False)
    assert _await_detach_activation() is True


def test_closed_issue_stops_before_graph_mutation(monkeypatch):
    monkeypatch.delenv("LOKAY_ISSUE_TO_PR_ACTIVATION_FD", raising=False)
    monkeypatch.setattr(issue_to_pr, "load_config", lambda _path: SimpleNamespace(mode="live"))
    monkeypatch.setattr(issue_to_pr, "_delivery_stop_reason", lambda _repo, _issue: "issue_closed")
    monkeypatch.setattr(
        issue_to_pr,
        "run_path",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("graph must not run")),
    )

    result = issue_to_pr.compose_issue_to_pr(
        config_path=None, repo="owner/repo", issue_number=329, live=True
    )

    assert result["ok"] is True
    assert result["stopped"] is True
    assert result["reason"] == "issue_closed"


def test_existing_on_goal_pr_is_a_delivery_stop(monkeypatch):
    def command_json(args):
        if args[1:3] == ["issue", "view"]:
            return {"state": "OPEN"}
        return [
            {"body": "Fixes #329", "state": "CLOSED", "mergedAt": "2025-01-01T00:00:00Z"},
            {"body": "Fixes #12", "state": "OPEN", "mergedAt": None},
        ]

    monkeypatch.setattr(issue_to_pr, "_command_json", command_json)
    monkeypatch.setattr(
        issue_to_pr,
        "_head_has_on_goal_src",
        lambda _repo, _issue: (_ for _ in ()).throw(AssertionError("HEAD must not be inspected")),
    )

    assert issue_to_pr._delivery_stop_reason("owner/repo", 329) == "delivery_pr_exists"
