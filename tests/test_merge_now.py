"""Hermetic tests for lokay-merge-now (subprocess mocked; no GitHub / Fala)."""

from __future__ import annotations


import json
from pathlib import Path
from types import SimpleNamespace

from lokay.proc import merge_now

REPO = "mikolaj92/lokay"
CMD = ["gh", "pr", "merge", "7", "--repo", REPO, "--merge"]


def _payload(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_dry_run_prints_command_and_does_not_call_gh(monkeypatch, capsys):
    def boom(*_a, **_k):
        raise AssertionError("gh must not run in dry-run")

    monkeypatch.setattr(merge_now.subprocess, "run", boom)
    code = merge_now.main(["--repo", REPO, "--pr", "7", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    payload = json.loads(out.strip().splitlines()[-1])
    assert payload["ok"] is True
    assert payload["planned"] is True
    assert payload["dry_run"] is True
    assert payload["merged"] is False
    assert payload["command"] == CMD
    assert "gh" in out and "pr" in out and "merge" in out
    assert REPO in out


def test_without_live_plans_and_does_not_call_gh(monkeypatch, capsys):
    """Hosted merge-now merges require healthy. Planned merges do not."""
    def boom(*_a, **_k):
        raise AssertionError("gh must not run without --live")

    monkeypatch.setattr(merge_now.subprocess, "run", boom)

    def health_boom(**_kwargs):
        raise AssertionError("planned merge must not require healthy")

    monkeypatch.setattr(merge_now, "mutations_allowed", health_boom)
    code = merge_now.main(["--repo", REPO, "--pr", "7"])
    assert code == 0
    payload = _payload(capsys)
    assert payload["ok"] is True
    assert payload["planned"] is True
    assert payload["merged"] is False
    src = Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc" / "merge_now.py"
    assert "Hosted merge-now merges require healthy. Planned merges do not." in src.read_text(
        encoding="utf-8"
    )




def test_merge_runs_exact_gh_argv(monkeypatch, capsys):
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        return SimpleNamespace(returncode=0, stdout="Merged\n", stderr="")

    monkeypatch.setattr(merge_now.subprocess, "run", fake_run)
    monkeypatch.setattr(merge_now, "load_cfg", lambda _args: SimpleNamespace())
    monkeypatch.setattr(merge_now, "mutations_allowed", lambda **_kwargs: True)
    code = merge_now.main(["--live", "--repo", REPO, "--pr", "7"])
    assert code == 0
    assert calls == [CMD]
    payload = _payload(capsys)
    assert payload["ok"] is True
    assert payload["merged"] is True
    assert payload["planned"] is False
    assert payload["command"] == CMD
    assert payload["repo"] == REPO
    assert payload["pr"] == 7


def test_live_requires_healthy_before_gh(monkeypatch, capsys):
    def boom(*_a, **_k):
        raise AssertionError("unhealthy merge must not call gh")

    monkeypatch.setattr(merge_now.subprocess, "run", boom)
    monkeypatch.setattr(merge_now, "load_cfg", lambda _args: SimpleNamespace())

    def reject(**_kwargs):
        raise RuntimeError("unhealthy")

    monkeypatch.setattr(merge_now, "mutations_allowed", reject)
    try:
        merge_now.main(["--live", "--repo", REPO, "--pr", "7"])
    except RuntimeError as exc:
        assert str(exc) == "unhealthy"
    else:
        raise AssertionError("unhealthy merge must fail closed")


def test_gh_nonzero_fails_closed(monkeypatch, capsys):
    def fake_run(argv, **kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="GraphQL: Pull Request is not mergeable\n",
        )

    monkeypatch.setattr(merge_now.subprocess, "run", fake_run)
    monkeypatch.setattr(merge_now, "load_cfg", lambda _args: SimpleNamespace())
    monkeypatch.setattr(merge_now, "mutations_allowed", lambda **_kwargs: True)
    code = merge_now.main(["--live", "--repo", REPO, "--pr", "7"])
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
    monkeypatch.setattr(merge_now, "load_cfg", lambda _args: SimpleNamespace())
    monkeypatch.setattr(merge_now, "mutations_allowed", lambda **_kwargs: True)
    code = merge_now.main(["--live", "--repo", REPO, "--pr", "7"])
    assert code == 1
    payload = _payload(capsys)
    assert payload["ok"] is False
    assert "gh" in payload["error"]
