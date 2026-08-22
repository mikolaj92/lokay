from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from lokay.proc import get_issue




def test_get_issue_still_fetches_lokay(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = object()
    issue = SimpleNamespace(to_dict=lambda: {"number": 459, "state": "OPEN"})
    sentinel_runner = object()
    seen: list[tuple[object, object, str, int, bool]] = []

    monkeypatch.setattr(get_issue, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(get_issue, "read_live", lambda _args: True)
    monkeypatch.setattr(get_issue, "runner", lambda: sentinel_runner)

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

    monkeypatch.setattr(get_issue, "get_issue", fake_get_issue)

    assert (
        get_issue.main(
            ["--repo", "mikolaj92/lokay", "--issue", "459", "--live"]
        )
        == 0
    )
    assert seen == [(sentinel_runner, cfg, "mikolaj92/lokay", 459, True)]
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "offline": False,
        "issue": {"number": 459, "state": "OPEN"},
    }
