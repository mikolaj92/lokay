"""Hermetic tests for lokay.proc.unbounded_park (gh mocked)."""

from __future__ import annotations

import json
from types import SimpleNamespace

from lokay.proc import unbounded_park


def _payload(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _gh(returncode: int = 0, stderr: str = "", stdout: str = ""):
    def run(argv):
        run.calls.append(list(argv))
        return SimpleNamespace(
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )

    run.calls = []
    return run


def test_dry_run_prints_gh_command_and_does_not_call_gh(monkeypatch, capsys):
    fake = _gh()
    monkeypatch.setattr(unbounded_park, "run_gh", fake)
    code = unbounded_park.main(
        ["--repo", "owner/name", "--issue", "12", "--dry-run"]
    )
    assert code == 0
    assert fake.calls == []
    payload = _payload(capsys)
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["applied"] is False
    assert payload["removed"] is False
    assert payload["label"] == "ai:ready"
    assert payload["command"] == (
        "gh issue edit 12 --repo owner/name --remove-label work:ready "
        "--remove-label ai:ready"
    )
    assert payload["argv"] == [
        "gh",
        "issue",
        "edit",
        "12",
        "--repo",
        "owner/name",
        "--remove-label",
        "work:ready",
        "--remove-label",
        "ai:ready",
    ]


def test_live_removes_ai_ready(monkeypatch, capsys):
    fake = _gh()
    monkeypatch.setattr(unbounded_park, "run_gh", fake)
    code = unbounded_park.main(["--repo", "owner/name", "--issue", "7"])
    assert code == 0
    assert fake.calls == [
        [
            "gh",
            "issue",
            "edit",
            "7",
            "--repo",
            "owner/name",
            "--remove-label",
            "work:ready",
            "--remove-label",
            "ai:ready",
        ]
    ]
    payload = _payload(capsys)
    assert payload["ok"] is True
    assert payload["dry_run"] is False
    assert payload["applied"] is True
    assert payload["removed"] is True
    assert payload["repo"] == "owner/name"
    assert payload["issue"] == 7


def test_missing_repo_fails_closed(monkeypatch, capsys):
    fake = _gh()
    monkeypatch.setattr(unbounded_park, "run_gh", fake)
    code = unbounded_park.main(["--issue", "1"])
    assert code == 1
    assert fake.calls == []
    payload = _payload(capsys)
    assert payload["ok"] is False
    assert "repo" in payload["error"]


def test_missing_issue_fails_closed(monkeypatch, capsys):
    fake = _gh()
    monkeypatch.setattr(unbounded_park, "run_gh", fake)
    code = unbounded_park.main(["--repo", "owner/name"])
    assert code == 1
    assert fake.calls == []
    payload = _payload(capsys)
    assert payload["ok"] is False
    assert "issue" in payload["error"]


def test_invalid_repo_fails_closed(monkeypatch, capsys):
    fake = _gh()
    monkeypatch.setattr(unbounded_park, "run_gh", fake)
    for repo in ("noslash", "owner/", "/name", "a/b/c"):
        code = unbounded_park.main(["--repo", repo, "--issue", "1"])
        assert code == 1
        assert fake.calls == []
        payload = _payload(capsys)
        assert payload["ok"] is False
        assert "owner/name" in payload["error"]


def test_non_positive_issue_fails_closed(monkeypatch, capsys):
    fake = _gh()
    monkeypatch.setattr(unbounded_park, "run_gh", fake)
    code = unbounded_park.main(["--repo", "owner/name", "--issue", "0"])
    assert code == 1
    assert fake.calls == []
    payload = _payload(capsys)
    assert payload["ok"] is False
    assert "issue" in payload["error"]


def test_gh_missing_issue_fails_closed(monkeypatch, capsys):
    fake = _gh(returncode=1, stderr="GraphQL: Could not resolve to an issue")
    monkeypatch.setattr(unbounded_park, "run_gh", fake)
    code = unbounded_park.main(["--repo", "owner/name", "--issue", "99"])
    assert code == 1
    payload = _payload(capsys)
    assert payload["ok"] is False
    assert payload["returncode"] == 1
    assert "issue not found" in payload["error"]
    assert fake.calls == [unbounded_park.park_argv("owner/name", 99)]


def test_dry_run_still_fail_closed_when_target_missing(monkeypatch, capsys):
    fake = _gh()
    monkeypatch.setattr(unbounded_park, "run_gh", fake)
    code = unbounded_park.main(["--dry-run"])
    assert code == 1
    assert fake.calls == []
    payload = _payload(capsys)
    assert payload["ok"] is False
    assert "repo" in payload["error"]
