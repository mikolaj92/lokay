"""Atomic pr_merge repository boundary."""

from __future__ import annotations

import json

import pytest

from lokay.proc import pr_merge


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
def test_product_repo_skips_without_gh_git_or_config(
    repo: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_if_called(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            "product repositories must not call GitHub, git, or config"
        )

    monkeypatch.setattr(pr_merge, "load_cfg", fail_if_called)
    monkeypatch.setattr(pr_merge, "mutations_allowed", fail_if_called)
    monkeypatch.setattr(pr_merge, "runner", fail_if_called)
    monkeypatch.setattr(pr_merge, "merge_pr", fail_if_called)
    monkeypatch.setattr(pr_merge, "run_proc", fail_if_called)

    assert (
        pr_merge.main(
            ["--repo", repo, "--pr", "522", "--issue", "522", "--live"]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "planned": False,
        "skipped": True,
        "reason": "repo_not_delivered_by_mini_mill",
        "repo": repo,
        "pr": 522,
        "merged": False,
        "issue": 522,
        "parked": None,
    }


def test_lokay_repo_still_merges_and_parks_issue(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = type("Cfg", (), {"merge_enabled": True})()
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
        pr_merge,
        "merge_pr",
        lambda merge_runner, repo, pr, *, live: merge_calls.append(
            (merge_runner, repo, pr, live)
        ),
    )

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
