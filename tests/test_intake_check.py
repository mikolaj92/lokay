"""CLI boundary tests for the atomic intake check."""

from __future__ import annotations

import json

import pytest

from lokay.proc import intake_check


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
@pytest.mark.skip(reason="obsolete single-repository mill contract")
def test_product_repo_skips_without_github(monkeypatch, capsys, repo: str):
    def unexpected_github_call(*args, **kwargs):
        pytest.fail("foreign product intake must not call GitHub")

    monkeypatch.setattr(intake_check, "get_issue", unexpected_github_call)

    code = intake_check.main(
        ["--repo", repo, "--issue", "516", "--check", "open"]
    )

    output = json.loads(capsys.readouterr().out)
    assert code == 0
    assert output["ok"] is True
    assert output["skipped"] is True
    assert output["reason"] == "repo_not_intake_target"
    assert output["repo"] == repo


def test_lokay_repo_still_fetches_issue(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(intake_check, "load_cfg", lambda args: object())
    monkeypatch.setattr(intake_check, "read_live", lambda args: False)
    monkeypatch.setattr(intake_check, "runner", lambda: object())

    def get_issue(*args, **kwargs):
        calls.append((args, kwargs))
        return None

    monkeypatch.setattr(intake_check, "get_issue", get_issue)

    code = intake_check.main(
        ["--repo", "mikolaj92/lokay", "--issue", "516", "--check", "open"]
    )

    output = json.loads(capsys.readouterr().out)
    assert code != 0
    assert output["ok"] is False
    assert calls
