from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from lokay.intake import IntakeDecision
from lokay.proc import intake_issue


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
def test_product_repo_skips_without_gh_or_config(
    repo: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_if_called(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("product repositories must not call GitHub or load config")

    monkeypatch.setattr(intake_issue, "load_cfg", fail_if_called)
    monkeypatch.setattr(intake_issue, "runner", fail_if_called)
    monkeypatch.setattr(intake_issue, "get_issue", fail_if_called)
    monkeypatch.setattr(intake_issue, "apply_intake", fail_if_called)

    assert intake_issue.main(["--repo", repo, "--issue", "508", "--live"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "planned": False,
        "skipped": True,
        "reason": "repo_not_delivered_by_mini_mill",
        "repo": repo,
        "issue": 508,
        "applied": False,
    }


def test_lokay_repo_still_runs_intake(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = SimpleNamespace(
        ready_label="ai:ready",
        needs_feedback_label="ai:needs-feedback",
        blocked_label="ai:blocked",
        branch_prefix="ai/",
        assignee="mikolaj92",
    )
    issue = SimpleNamespace(
        labels=["ai:ready"],
        state="OPEN",
        to_dict=lambda: {"repo": "mikolaj92/lokay", "number": 508},
    )
    decision = IntakeDecision(
        decision="ready",
        reason="spec_ok",
        implementable=True,
    )
    sentinel_runner = object()
    seen: list[tuple[object, object, str, int, bool]] = []

    monkeypatch.setattr(intake_issue, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(intake_issue, "runner", lambda: sentinel_runner)
    monkeypatch.setattr(intake_issue, "read_live", lambda _args: True)
    monkeypatch.setattr(
        intake_issue,
        "mutations_allowed",
        lambda *, live_flag, cfg: live_flag,
    )

    def fake_get_issue(
        issue_runner: object,
        loaded_cfg: object,
        repo: str,
        number: int,
        *,
        live: bool,
    ) -> object:
        seen.append((issue_runner, loaded_cfg, repo, number, live))
        return issue

    monkeypatch.setattr(intake_issue, "get_issue", fake_get_issue)
    monkeypatch.setattr(intake_issue, "referenced_pr_numbers", lambda _issue: [])
    monkeypatch.setattr(intake_issue, "merged_prs", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(intake_issue, "covering_ai_prs", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(intake_issue, "resolve_repo_clone", lambda *_args: None)
    monkeypatch.setattr(intake_issue, "semantic_agent_allowed", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(intake_issue, "decide_intake_with_agent", lambda *_args, **_kwargs: decision)
    monkeypatch.setattr(intake_issue, "apply_intake", lambda *_args, **_kwargs: True)

    assert (
        intake_issue.main(
            ["--repo", "mikolaj92/lokay", "--issue", "508", "--live"]
        )
        == 0
    )
    assert seen == [(sentinel_runner, cfg, "mikolaj92/lokay", 508, True)]
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["repo"] == "mikolaj92/lokay"
    assert payload["applied"] is True
    assert payload["decision"]["decision"] == "ready"


def test_covering_pr_probe_failure_stops_intake_before_decision(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = SimpleNamespace(
        ready_label="ai:ready",
        needs_feedback_label="ai:needs-feedback",
        blocked_label="ai:blocked",
        branch_prefix="ai/",
        assignee="mikolaj92",
    )
    issue = SimpleNamespace(
        labels=["ai:ready"],
        state="OPEN",
        to_dict=lambda: {"repo": "mikolaj92/lokay", "number": 508},
    )
    monkeypatch.setattr(intake_issue, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(intake_issue, "runner", lambda: object())
    monkeypatch.setattr(intake_issue, "read_live", lambda _args: True)
    monkeypatch.setattr(
        intake_issue, "mutations_allowed", lambda *, live_flag, cfg: live_flag
    )
    monkeypatch.setattr(intake_issue, "get_issue", lambda *_args, **_kwargs: issue)
    monkeypatch.setattr(intake_issue, "resolve_repo_clone", lambda *_args: None)
    monkeypatch.setattr(intake_issue, "referenced_pr_numbers", lambda _issue: [])
    monkeypatch.setattr(intake_issue, "merged_prs", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        intake_issue,
        "covering_ai_prs",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("probe failed")),
    )
    monkeypatch.setattr(
        intake_issue,
        "decide_intake_with_agent",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("uncertain evidence must not reach intake decision")
        ),
    )

    assert intake_issue.main(["--repo", "mikolaj92/lokay", "--issue", "508", "--live"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["probe_failed"] is True
    assert payload["error"] == "probe failed"
