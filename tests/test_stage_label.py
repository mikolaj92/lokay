"""Hermetic repository-boundary tests for lokay-stage-label."""

from __future__ import annotations

import json

import pytest

from lokay.proc import stage_label


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
def test_product_repo_skips_without_github_calls(repo, monkeypatch, capsys):
    def unexpected(*args, **kwargs):
        raise AssertionError("foreign repositories must be skipped before GitHub access")

    monkeypatch.setattr(stage_label, "load_cfg", unexpected)
    monkeypatch.setattr(stage_label, "runner", unexpected)
    monkeypatch.setattr(stage_label, "get_issue", unexpected)
    monkeypatch.setattr(stage_label, "add_issue_labels", unexpected)
    monkeypatch.setattr(stage_label, "remove_issue_labels", unexpected)
    monkeypatch.setattr(stage_label, "comment_issue", unexpected)

    code = stage_label.main(
        [
            "--repo",
            repo,
            "--issue",
            "502",
            "--stage",
            "ready",
            "--receipt",
            "--live",
        ]
    )

    assert code == 0
    envelope = json.loads(capsys.readouterr().out.strip())
    assert envelope == {
        "ok": True,
        "planned": False,
        "skipped": True,
        "reason": "repo_not_delivered_by_mini_mill",
        "repo": repo,
        "issue": 502,
        "stage": "ready",
        "add_labels": [],
        "remove_labels": [],
        "receipt": False,
        "applied": False,
    }
