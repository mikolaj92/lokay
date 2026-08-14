"""Abandoned ai:in-progress must return to ready — drive shipped policy + atom."""

from __future__ import annotations

from types import SimpleNamespace

from lokay.models import Issue
from lokay.proc.reap_stale_implementing import run_reap_stale_implementing
from lokay.stale_implementing import issue_has_covering_pr, should_reap_implementing


def test_reap_when_no_job_and_no_pr():
    assert should_reap_implementing(has_live_job=False, has_covering_pr=False) is True


def test_keep_when_live_job_or_pr():
    assert should_reap_implementing(has_live_job=True, has_covering_pr=False) is False
    assert should_reap_implementing(has_live_job=False, has_covering_pr=True) is False


def test_covering_pr_from_branch_and_title():
    prs = [{"head_ref": "ai/fix/164-src-readme", "title": "fix: other"}]
    assert issue_has_covering_pr(164, prs) is True
    assert issue_has_covering_pr(91, [{"head_ref": "ai/fix/1-x", "title": "fix: repo#91 foo"}]) is True
    assert issue_has_covering_pr(91, [{"head_ref": "ai/fix/1-x", "title": "unrelated"}]) is False


def test_atom_reaps_stale_and_keeps_live(tmp_path, monkeypatch):
    issue = Issue(
        repo="mikolaj92/Fala",
        number=164,
        title="readme",
        body="",
        labels=["ai:in-progress"],
        assignees=["mikolaj92"],
        url="https://example.test/164",
    )
    live = Issue(
        repo="mikolaj92/Fala",
        number=99,
        title="live",
        body="",
        labels=["ai:in-progress"],
        assignees=["mikolaj92"],
        url="https://example.test/99",
    )
    monkeypatch.setattr(
        "lokay.proc.reap_stale_implementing.list_labeled_issues",
        lambda *a, **k: [issue, live],
    )
    monkeypatch.setattr(
        "lokay.proc.reap_stale_implementing._live_job_keys",
        lambda: {("mikolaj92/Fala", 99)},
    )
    monkeypatch.setattr(
        "lokay.proc.reap_stale_implementing.load_cfg",
        lambda args: SimpleNamespace(
            branch_prefix="ai/fix",
            active_repos=lambda: [SimpleNamespace(name="mikolaj92/Fala")],
        ),
    )
    staged: list[list[str]] = []

    def fake_proc(main, argv):
        staged.append(argv)
        return {"ok": True, "stage": "ready", "applied": True}

    monkeypatch.setattr("lokay.proc.reap_stale_implementing.run_proc", fake_proc)
    out = run_reap_stale_implementing(pass_dir=None, config_path=None, live=True)
    assert out["ok"] is True
    assert out["reaped_count"] == 1
    assert out["reaped"][0]["issue"] == 164
    assert out["kept"][0]["issue"] == 99
    assert any("--stage" in a and "ready" in a for a in staged)
