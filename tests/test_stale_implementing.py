"""Abandoned in-flight ledger stages must return to ready — drive shipped policy + atom."""

from __future__ import annotations

from types import SimpleNamespace

from lokay.models import Issue
from lokay.proc.reap_stale_implementing import run_reap_stale_implementing
from lokay.stage_ledger import LABEL_IMPLEMENTING, LABEL_PR_OPEN
from lokay.stale_implementing import (
    issue_has_covering_pr,
    should_reap_implementing,
    should_reap_pr_open,
)


def test_reap_when_no_job_and_no_pr():
    assert should_reap_implementing(has_live_job=False, has_covering_pr=False) is True
    assert should_reap_pr_open(has_live_job=False, has_covering_pr=False) is True


def test_keep_when_live_job_or_pr():
    assert should_reap_implementing(has_live_job=True, has_covering_pr=False) is False
    assert should_reap_implementing(has_live_job=False, has_covering_pr=True) is False
    assert should_reap_pr_open(has_live_job=True, has_covering_pr=False) is False
    assert should_reap_pr_open(has_live_job=False, has_covering_pr=True) is False


def test_covering_pr_from_branch_and_title():
    prs = [{"head_ref": "ai/fix/164-src-readme", "title": "fix: other"}]
    assert issue_has_covering_pr(164, prs) is True
    assert issue_has_covering_pr(91, [{"head_ref": "ai/fix/1-x", "title": "fix: repo#91 foo"}]) is True
    assert issue_has_covering_pr(91, [{"head_ref": "ai/fix/1-x", "title": "unrelated"}]) is False


def _issue(number: int, title: str, labels: list[str]) -> Issue:
    return Issue(
        repo="mikolaj92/lokay",
        number=number,
        title=title,
        body="",
        labels=labels,
        assignees=["mikolaj92"],
        url=f"https://example.test/{number}",
    )


def test_atom_strips_leftover_cache_even_when_job_or_pr_exists(monkeypatch):
    leftover = _issue(164, "readme", [LABEL_IMPLEMENTING])
    also = _issue(21, "pr cache", [LABEL_PR_OPEN])
    by_label = {
        LABEL_IMPLEMENTING: [leftover],
        LABEL_PR_OPEN: [also],
    }
    monkeypatch.setattr(
        "lokay.proc.reap_stale_implementing.list_labeled_issues",
        lambda *a, **k: list(by_label.get(k.get("label"), [])),
    )
    monkeypatch.setattr(
        "lokay.proc.reap_stale_implementing.load_cfg",
        lambda args: SimpleNamespace(
            branch_prefix="ai/fix",
            active_repos=lambda: [SimpleNamespace(name="mikolaj92/lokay")],
        ),
    )
    staged: list[list[str]] = []

    def fake_proc(main, argv):
        staged.append(argv)
        return {"ok": True, "stage": "ready", "applied": True}

    monkeypatch.setattr("lokay.proc.reap_stale_implementing.run_proc", fake_proc)
    out = run_reap_stale_implementing(pass_dir=None, config_path=None, live=True)
    assert out["ok"] is True
    assert out["reaped_count"] == 2
    assert {row["issue"] for row in out["reaped"]} == {164, 21}
    assert out["kept"] == []
    assert any("164" in a and "ready" in a for a in staged)
