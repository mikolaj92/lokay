from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from lokay.proc import assign_issue




def test_assign_issue_still_assigns_lokay(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = SimpleNamespace(assignee="lokay-bot")
    sentinel_runner = object()
    seen: list[tuple[object, object, str, int, bool]] = []

    monkeypatch.setattr(assign_issue, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(
        assign_issue, "mutations_allowed", lambda *, live_flag, cfg: live_flag
    )
    monkeypatch.setattr(assign_issue, "runner", lambda: sentinel_runner)
    monkeypatch.setattr(
        assign_issue, "get_issue", lambda *_a, **_k: SimpleNamespace(assignees=[])
    )

    def fake_assign_issue(
        issue_runner: object,
        loaded_cfg: object,
        repo: str,
        issue: int,
        *,
        live: bool,
    ) -> None:
        seen.append((issue_runner, loaded_cfg, repo, issue, live))

    monkeypatch.setattr(assign_issue, "assign_issue", fake_assign_issue)

    assert (
        assign_issue.main(
            ["--repo", "mikolaj92/lokay", "--issue", "465", "--live"]
        )
        == 0
    )
    assert seen == [(sentinel_runner, cfg, "mikolaj92/lokay", 465, True)]
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "planned": False,
        "applied": True,
        "repo": "mikolaj92/lokay",
        "issue": 465,
        "assignee": "lokay-bot",
    }


def test_assign_issue_refuses_foreign_owned(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = SimpleNamespace(assignee="mikolaj92")
    seen: list[object] = []

    monkeypatch.setattr(assign_issue, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(
        assign_issue, "mutations_allowed", lambda *, live_flag, cfg: live_flag
    )
    monkeypatch.setattr(assign_issue, "runner", lambda: object())
    monkeypatch.setattr(
        assign_issue,
        "get_issue",
        lambda *_a, **_k: SimpleNamespace(assignees=["PSyron"]),
    )
    monkeypatch.setattr(
        assign_issue, "assign_issue", lambda *_a, **_k: seen.append("assigned")
    )

    assert (
        assign_issue.main(
            ["--repo", "Temida/Temida", "--issue", "5072", "--live"]
        )
        != 0
    )
    assert seen == []
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"] == "foreign_assignee"
    assert payload["applied"] is False
    assert payload["assignees"] == ["PSyron"]


def test_assign_issue_refuses_pawel_beside_lokaj(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = SimpleNamespace(assignee="mikolaj92")
    seen: list[object] = []

    monkeypatch.setattr(assign_issue, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(
        assign_issue, "mutations_allowed", lambda *, live_flag, cfg: live_flag
    )
    monkeypatch.setattr(assign_issue, "runner", lambda: object())
    monkeypatch.setattr(
        assign_issue,
        "get_issue",
        lambda *_a, **_k: SimpleNamespace(assignees=["PSyron", "mikolaj92"]),
    )
    monkeypatch.setattr(
        assign_issue, "assign_issue", lambda *_a, **_k: seen.append("assigned")
    )

    assert (
        assign_issue.main(["--repo", "Temida/Temida", "--issue", "5072", "--live"])
        != 0
    )
    assert seen == []
    assert json.loads(capsys.readouterr().out)["error"] == "foreign_assignee"
