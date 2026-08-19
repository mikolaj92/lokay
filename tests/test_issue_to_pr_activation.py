"""Detached issue-to-PR activation barrier."""

from __future__ import annotations

import os
import subprocess
from types import SimpleNamespace

import pytest

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


def test_unavailable_delivery_survey_does_not_stop_implementation(monkeypatch):
    monkeypatch.delenv("LOKAY_ISSUE_TO_PR_ACTIVATION_FD", raising=False)
    monkeypatch.setattr(
        issue_to_pr,
        "load_config",
        lambda _path: SimpleNamespace(mode="live", state_path="state.jsonl"),
    )
    monkeypatch.setattr(issue_to_pr, "_command_json", lambda _args: None)
    monkeypatch.setattr(issue_to_pr, "_head_has_on_goal_src", lambda _repo, _issue: False)
    monkeypatch.setattr(issue_to_pr, "run_path", lambda **_kwargs: {"ok": True})
    monkeypatch.setattr(issue_to_pr, "append_event", lambda _path, _result: None)

    result = issue_to_pr.compose_issue_to_pr(
        config_path=None, repo="owner/repo", issue_number=331, live=True
    )

    assert result["ok"] is True
    assert result.get("stopped") is not True
    assert result.get("reason") != "delivery_survey_unavailable"


def test_confirmed_closed_issue_remains_a_delivery_stop(monkeypatch):
    monkeypatch.setattr(issue_to_pr, "_command_json", lambda _args: {"state": "CLOSED"})

    assert issue_to_pr._delivery_stop_reason("owner/repo", 331) == "issue_closed"


def test_on_goal_src_in_earlier_branch_commit_is_a_delivery_stop(tmp_path, monkeypatch):
    def git(*args):
        subprocess.run(
            ["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True
        )

    git("init", "-b", "main")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.com")
    git("remote", "add", "origin", "https://github.com/owner/repo.git")
    (tmp_path / "README.md").write_text("base\n", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-m", "base")
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    git("switch", "-c", "ai/fix/363-issue")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("value = 1\n", encoding="utf-8")
    git("add", "src/foo.py")
    git("commit", "-m", "implement fix")
    (tmp_path / ".lokay").mkdir()
    (tmp_path / ".lokay" / "approach.md").write_text("plan\n", encoding="utf-8")
    git("add", ".lokay/approach.md")
    git("commit", "-m", "record approach")
    monkeypatch.chdir(tmp_path)

    assert issue_to_pr._head_has_on_goal_src("owner/repo", 363) is True


@pytest.mark.parametrize(
    ("body", "state", "merged_at"),
    [
        ("Fixes #329", "CLOSED", "2025-01-01T00:00:00Z"),
        ("Closes #329", "OPEN", None),
        ("resolves #329", "OPEN", None),
    ],
)
def test_existing_on_goal_pr_is_a_delivery_stop(
    monkeypatch, body, state, merged_at
):
    def command_json(args):
        if args[1:3] == ["issue", "view"]:
            return {"state": "OPEN"}
        return [
            {"body": body, "state": state, "mergedAt": merged_at},
            {"body": "Fixes #12", "state": "OPEN", "mergedAt": None},
        ]

    monkeypatch.setattr(issue_to_pr, "_command_json", command_json)
    monkeypatch.setattr(
        issue_to_pr,
        "_head_has_on_goal_src",
        lambda _repo, _issue: (_ for _ in ()).throw(AssertionError("HEAD must not be inspected")),
    )

    assert issue_to_pr._delivery_stop_reason("owner/repo", 329) == "delivery_pr_exists"
