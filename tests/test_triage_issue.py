from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from lokay.proc import triage_issue


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
def test_product_repo_skips_without_gh_or_config(
    repo: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_if_called(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("product repositories must not call GitHub or load config")

    monkeypatch.setattr(triage_issue, "load_cfg", fail_if_called)
    monkeypatch.setattr(triage_issue, "mutations_allowed", fail_if_called)
    monkeypatch.setattr(triage_issue, "runner", fail_if_called)
    monkeypatch.setattr(triage_issue, "get_issue", fail_if_called)
    monkeypatch.setattr(triage_issue, "add_issue_labels", fail_if_called)
    monkeypatch.setattr(triage_issue, "assign_issue", fail_if_called)
    monkeypatch.setattr(triage_issue, "comment_issue", fail_if_called)
    monkeypatch.setattr(triage_issue, "close_issue", fail_if_called)

    assert triage_issue.main(["--repo", repo, "--issue", "506", "--live"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "planned": False,
        "skipped": True,
        "reason": "repo_not_delivered_by_mini_mill",
        "repo": repo,
        "issue": 506,
        "applied": False,
    }


def test_lokay_repo_still_triages_and_applies(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = SimpleNamespace(
        ready_label="ai:ready",
        blocked_label="ai:blocked",
        needs_feedback_label="ai:needs-feedback",
        assignee=None,
    )
    issue = SimpleNamespace(
        labels=[],
        title="Implement requested fix",
        body="Please implement this bounded fix with a regression test.",
        to_dict=lambda: {"repo": "mikolaj92/lokay", "number": 506},
    )
    sentinel_runner = object()
    calls: list[tuple[object, str, int, list[str], bool]] = []

    monkeypatch.setattr(triage_issue, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(
        triage_issue,
        "mutations_allowed",
        lambda *, live_flag, cfg: live_flag,
    )
    monkeypatch.setattr(triage_issue, "runner", lambda: sentinel_runner)
    monkeypatch.setattr(triage_issue, "get_issue", lambda *_args, **_kwargs: issue)
    monkeypatch.setattr(
        triage_issue,
        "add_issue_labels",
        lambda issue_runner, repo, number, labels, *, live: calls.append(
            (issue_runner, repo, number, labels, live)
        ),
    )

    assert (
        triage_issue.main(
            ["--repo", "mikolaj92/lokay", "--issue", "506", "--live"]
        )
        == 0
    )
    assert calls == [
        (sentinel_runner, "mikolaj92/lokay", 506, ["ai:ready"], True)
    ]
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["applied"] is True
    assert payload["repo"] == "mikolaj92/lokay"
    assert payload["decision"]["decision"] == "ready"
