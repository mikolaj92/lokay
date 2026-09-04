"""Atomic pr_merge repository boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lokay.code import github as github_code
from lokay.proc import pr_merge


def test_factory_repo_still_merges_and_parks_issue(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = type("Cfg", (), {"merge_enabled": True, "repos": [], "worktrees_root": Path("/tmp")})()
    sentinel_runner = object()
    merge_calls: list[tuple[object, str, int, bool]] = []
    park_calls: list[tuple[object, list[str]]] = []

    monkeypatch.setattr(pr_merge, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(
        pr_merge,
        "mutations_allowed",
        lambda *, live_flag, cfg: live_flag,
    )
    monkeypatch.setattr(pr_merge, "runner", lambda: sentinel_runner)
    monkeypatch.setattr(
        github_code,
        "merge_pr",
        lambda merge_runner, repo, pr, *, live: merge_calls.append(
            (merge_runner, repo, pr, live)
        ),
    )
    monkeypatch.setattr(github_code, "view_pr", lambda *_a, **_k: {})

    def park(proc: object, argv: list[str]) -> dict[str, bool]:
        park_calls.append((proc, argv))
        return {"ok": True}

    monkeypatch.setattr(pr_merge, "run_proc", park)

    assert (
        pr_merge.main(
            [
                "--repo",
                "mikolaj92/lokay",
                "--pr",
                "522",
                "--issue",
                "522",
                "--live",
            ]
        )
        == 0
    )
    assert merge_calls == [(sentinel_runner, "mikolaj92/lokay", 522, True)]
    assert park_calls == [
        (
            pr_merge.unbounded_park.main,
            ["--live", "--repo", "mikolaj92/lokay", "--issue", "522"],
        )
    ]
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "planned": False,
        "repo": "mikolaj92/lokay",
        "pr": 522,
        "merged": True,
        "issue": 522,
        "parked": {"ok": True},
    }
