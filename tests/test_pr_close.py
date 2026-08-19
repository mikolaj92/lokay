"""Atomic pr_close repository boundary."""

from __future__ import annotations

import json

import pytest

from lokay.proc import pr_close


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
def test_product_repo_skips_without_gh_or_config(
    repo: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_if_called(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("product repositories must not call GitHub or load config")

    monkeypatch.setattr(pr_close, "load_cfg", fail_if_called)
    monkeypatch.setattr(pr_close, "mutations_allowed", fail_if_called)
    monkeypatch.setattr(pr_close, "runner", fail_if_called)
    monkeypatch.setattr(pr_close, "close_pr", fail_if_called)

    assert (
        pr_close.main(
            [
                "--repo",
                repo,
                "--pr",
                "478",
                "--comment",
                "conflict",
                "--live",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "planned": False,
        "skipped": True,
        "reason": "repo_not_delivered_by_mini_mill",
        "repo": repo,
        "pr": 478,
        "closed": False,
    }


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
        pr_close,
        "close_pr",
        lambda close_runner, repo, pr, *, live, comment: calls.append(
            (close_runner, repo, pr, live, comment)
        ),
    )

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
