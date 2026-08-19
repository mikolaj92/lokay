from __future__ import annotations

import json

import pytest

from lokay.proc import label_issue


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
def test_label_issue_skips_product_repo_without_gh(
    repo: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_if_called(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("product repositories must not call GitHub")

    monkeypatch.setattr(label_issue, "load_cfg", fail_if_called)
    monkeypatch.setattr(label_issue, "mutations_allowed", fail_if_called)
    monkeypatch.setattr(label_issue, "runner", fail_if_called)
    monkeypatch.setattr(label_issue, "add_issue_labels", fail_if_called)
    monkeypatch.setattr(label_issue, "remove_issue_labels", fail_if_called)

    assert (
        label_issue.main(
            ["--repo", repo, "--issue", "463", "--label", "work:ready", "--live"]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "planned": False,
        "skipped": True,
        "reason": "repo_not_delivered_by_mini_mill",
        "repo": repo,
        "issue": 463,
        "labels": ["work:ready"],
        "removed": False,
        "applied": False,
    }


@pytest.mark.parametrize("remove", [False, True])
def test_label_issue_still_updates_lokay(
    remove: bool,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = object()
    sentinel_runner = object()
    calls: list[tuple[str, object, str, int, list[str], bool]] = []

    monkeypatch.setattr(label_issue, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(
        label_issue,
        "mutations_allowed",
        lambda *, live_flag, cfg: live_flag,
    )
    monkeypatch.setattr(label_issue, "runner", lambda: sentinel_runner)
    monkeypatch.setattr(
        label_issue,
        "add_issue_labels",
        lambda issue_runner, repo, issue, labels, *, live: calls.append(
            ("add", issue_runner, repo, issue, labels, live)
        ),
    )
    monkeypatch.setattr(
        label_issue,
        "remove_issue_labels",
        lambda issue_runner, repo, issue, labels, *, live: calls.append(
            ("remove", issue_runner, repo, issue, labels, live)
        ),
    )

    argv = [
        "--repo",
        "mikolaj92/lokay",
        "--issue",
        "463",
        "--label",
        "work:ready",
        "--label",
        "ai:ready",
        "--live",
    ]
    if remove:
        argv.append("--remove")

    assert label_issue.main(argv) == 0
    assert calls == [
        (
            "remove" if remove else "add",
            sentinel_runner,
            "mikolaj92/lokay",
            463,
            ["work:ready", "ai:ready"],
            True,
        )
    ]
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "planned": False,
        "repo": "mikolaj92/lokay",
        "issue": 463,
        "labels": ["work:ready", "ai:ready"],
        "removed": remove,
        "applied": True,
    }
