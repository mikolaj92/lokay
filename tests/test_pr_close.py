"""Atomic pr_close repository boundary."""

from __future__ import annotations

import json

import pytest

from lokay.code import github as github_code
from lokay.proc import pr_close


def test_lokay_repo_still_closes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = object()
    sentinel_runner = object()
    calls: list[tuple[object, str, int, bool, str]] = []

    monkeypatch.setattr(pr_close, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(
        pr_close,
        "mutations_allowed",
        lambda *, live_flag, cfg: live_flag,
    )
    monkeypatch.setattr(pr_close, "runner", lambda: sentinel_runner)
    monkeypatch.setattr(
        github_code,
        "close_pr",
        lambda close_runner, repo, pr, *, live, comment: calls.append(
            (close_runner, repo, pr, live, comment)
        ),
    )
    monkeypatch.setattr(github_code, "view_pr", lambda *_a, **_k: {})

    assert (
        pr_close.main(
            [
                "--repo",
                "mikolaj92/lokay",
                "--pr",
                "478",
                "--comment",
                "conflict",
                "--live",
            ]
        )
        == 0
    )
    assert calls == [
        (sentinel_runner, "mikolaj92/lokay", 478, True, "conflict")
    ]
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "planned": False,
        "repo": "mikolaj92/lokay",
        "pr": 478,
        "closed": True,
    }


def test_pr_close_dry_run() -> None:
    # No network: mutations_allowed false without --live.
    assert (
        pr_close.main(
            ["--repo", "mikolaj92/lokay", "--pr", "4", "--comment", "test"]
        )
        == 0
    )
