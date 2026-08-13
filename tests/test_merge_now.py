"""Hermetic tests for lokay-merge-now (subprocess mocked; no GitHub / Fala)."""

from __future__ import annotations

import json
from types import SimpleNamespace

from lokay.proc import merge_now

CMD = ["gh", "pr", "merge", "7", "--repo", "owner/name", "--merge"]


def _payload(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_dry_run_prints_command_and_does_not_call_gh(monkeypatch, capsys):
    def boom(*_a, **_k):
        raise AssertionError("gh must not run in dry-run")

    monkeypatch.setattr(merge_now.subprocess, "run", boom)
    code = merge_now.main(["--repo", "owner/name", "--pr", "7", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    payload = json.loads(out.strip().splitlines()[-1])
    assert payload["ok"] is True
    assert payload["planned"] is True
    assert payload["dry_run"] is True
    assert payload["command"] == CMD
    assert "gh" in out and "pr" in out and "merge" in out
    assert "owner/name" in out


def test_merge_runs_exact_gh_argv(monkeypatch, capsys):
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        return SimpleNamespace(returncode=0, stdout="Merged\n", stderr="")

    monkeypatch.setattr(merge_now.subprocess, "run", fake_run)
    code = merge_now.main(["--repo", "owner/name", "--pr", "7"])
    assert code == 0
    assert calls == [CMD]
    payload = _payload(capsys)
    assert payload["ok"] is True
    assert payload["merged"] is True
    assert payload["planned"] is False
    assert payload["command"] == CMD
    assert payload["repo"] == "owner/name"
    assert payload["pr"] == 7


def test_gh_nonzero_fails_closed(monkeypatch, capsys):
    def fake_run(argv, **kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="GraphQL: Pull Request is not mergeable\n",
        )

    monkeypatch.setattr(merge_now.subprocess, "run", fake_run)
    code = merge_now.main(["--repo", "owner/name", "--pr", "7"])
    assert code == 1
    payload = _payload(capsys)
    assert payload["ok"] is False
    assert "not mergeable" in payload["error"]
    assert payload["returncode"] == 1
    assert payload["command"] == CMD


def test_missing_gh_fails_closed(monkeypatch, capsys):
    def fake_run(argv, **kwargs):
        raise FileNotFoundError("No such file or directory: 'gh'")

    monkeypatch.setattr(merge_now.subprocess, "run", fake_run)
    code = merge_now.main(["--repo", "owner/name", "--pr", "7"])
    assert code == 1
    payload = _payload(capsys)
    assert payload["ok"] is False
    assert "gh" in payload["error"]
