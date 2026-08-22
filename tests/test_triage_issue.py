from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from lokay.proc import triage_issue




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
        (sentinel_runner, "mikolaj92/lokay", 506, ["ai:ready", "work:ready"], True)
    ]
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["applied"] is True
    assert payload["repo"] == "mikolaj92/lokay"
    assert payload["decision"]["decision"] == "ready"
