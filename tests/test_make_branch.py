from __future__ import annotations

import json

import pytest

from lokay.proc import make_branch




def test_make_branch_still_makes_lokay_branch(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[tuple[str, str, int, str]] = []

    def make(prefix: str, repo: str, issue: int, title: str) -> str:
        calls.append((prefix, repo, issue, title))
        return "ai/fix/492-fix-12345678"

    monkeypatch.setattr(make_branch, "branch_for_issue", make)

    assert make_branch.main(
        [
            "--prefix",
            "ai/fix",
            "--repo",
            "mikolaj92/lokay",
            "--issue",
            "492",
            "--title",
            "Fix",
        ]
    ) == 0
    assert calls == [("ai/fix", "mikolaj92/lokay", 492, "Fix")]
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "branch": "ai/fix/492-fix-12345678",
        "repo": "mikolaj92/lokay",
        "issue": 492,
    }
