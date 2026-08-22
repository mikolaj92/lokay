from __future__ import annotations

import json

import pytest

from lokay.proc import make_branch


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
@pytest.mark.skip(reason="obsolete single-repository mill contract")
def test_make_branch_skips_product_repo_without_making_branch(
    repo: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_if_called(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("product repositories must not make a branch")

    monkeypatch.setattr(make_branch, "branch_for_issue", fail_if_called)

    assert make_branch.main(["--repo", repo, "--issue", "492", "--title", "ignored"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "skipped": True,
        "reason": "repo_not_delivered_by_mini_mill",
        "repo": repo,
        "issue": 492,
    }


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
