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
    assert (
        issue_has_covering_pr(
            91, [{"head_ref": "ai/fix/1-x", "title": "fix: repo#91 foo"}]
        )
        is True
    )
    assert (
        issue_has_covering_pr(91, [{"head_ref": "ai/fix/1-x", "title": "unrelated"}])
        is False
    )


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


def test_label_probes_reduce_and_each_candidate_restores_ready(monkeypatch):
    from lokay.proc.reduce_stale_repo_probe import reduce_state as reduce_repo
    from lokay.proc.reduce_stale_implementing_probe import reduce_state as reduce_all
    from lokay.proc.select_stale_candidate_slot import select
    from lokay.proc.restore_stale_issue_ready import restore

    rows = [
        {
            "route": "listed",
            "issues": [
                {"repo": "mikolaj92/lokay", "issue": 164, "label": LABEL_IMPLEMENTING}
            ],
        },
        {
            "route": "listed",
            "issues": [
                {"repo": "mikolaj92/lokay", "issue": 21, "label": LABEL_PR_OPEN}
            ],
        },
    ]
    repo = reduce_repo({"route": "repo", "repo": "mikolaj92/lokay"}, rows)
    probe = reduce_all(prepared={}, rows=[repo], candidate_slots=30)
    staged = []
    monkeypatch.setattr(
        "lokay.proc.restore_stale_issue_ready.run_proc",
        lambda main, argv: staged.append(argv)
        or {"ok": True, "stage": "ready", "applied": True},
    )
    for slot in (1, 2):
        restore(select(probe, {"apply": True}, slot=slot), config_path=None, live=True)
    assert {x["issue"] for x in probe["candidates"]} == {164, 21} and any(
        "164" in a and "ready" in a for a in staged
    )
