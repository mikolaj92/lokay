"""Detached issue-to-PR activation barrier."""

from __future__ import annotations

import os

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
