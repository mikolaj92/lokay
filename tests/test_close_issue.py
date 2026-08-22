from __future__ import annotations

import json

import pytest

from lokay.proc import close_issue




def test_close_issue_still_closes_lokay(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = object()
    sentinel_runner = object()
    calls: list[tuple[str, object, str, int, str | None, bool]] = []

    monkeypatch.setattr(close_issue, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(
        close_issue,
        "mutations_allowed",
        lambda *, live_flag, cfg: live_flag,
    )
    monkeypatch.setattr(close_issue, "runner", lambda: sentinel_runner)
    monkeypatch.setattr(
        close_issue,
        "comment_issue",
        lambda issue_runner, repo, issue, comment, *, live: calls.append(
            ("comment", issue_runner, repo, issue, comment, live)
        ),
    )
    monkeypatch.setattr(
        close_issue,
        "close_issue",
        lambda issue_runner, repo, issue, *, live: calls.append(
            ("close", issue_runner, repo, issue, None, live)
        ),
    )

    assert (
        close_issue.main(
            [
                "--repo",
                "mikolaj92/lokay",
                "--issue",
                "467",
                "--comment",
                "done",
                "--live",
            ]
        )
        == 0
    )
    assert calls == [
        ("comment", sentinel_runner, "mikolaj92/lokay", 467, "done", True),
        ("close", sentinel_runner, "mikolaj92/lokay", 467, None, True),
    ]
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "planned": False,
        "repo": "mikolaj92/lokay",
        "issue": 467,
        "closed": True,
    }
