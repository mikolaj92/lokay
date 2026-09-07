"""#1086: dual-ready leftover must fill ready_by_repo and start issue→PR."""

from __future__ import annotations

from lokay.execution_contracts import CATALOG_SLOT_COUNT
from lokay.proc.catalog_work import (
    ready_by_repo_from_leftover,
    remaining_ready_count,
    work_by_repo,
)
from lokay.proc.leftover_ready_contract import classify_leftover_ready_contract
from lokay.proc.seed_prior_catalog import seed_ready_from_leftover
from lokay.proc.select_next_issue import select
from lokay.proc.walk_issue_leftover import queue, ready_first


def _dual(repo: str, issue: int) -> dict:
    return {
        "repo": repo,
        "issue": issue,
        "number": issue,
        "labels": ["ai:ready", "work:ready"],
        "title": f"{repo}#{issue}",
        "assignees": ["mikolaj92"],
    }


def _plain(repo: str, issue: int) -> dict:
    return {
        "repo": repo,
        "issue": issue,
        "number": issue,
        "labels": ["kind:docs"],
        "title": f"{repo}#{issue}",
        "assignees": ["mikolaj92"],
    }


def test_ready_first_beats_unlabeled_leftover():
    rows = [
        _plain("mikolaj92/Temida", 5637),
        _plain("mikolaj92/Temida", 5682),
        _dual("mikolaj92/Temida", 5714),
    ]
    assert [row["issue"] for row in ready_first(rows)] == [5714]


def test_queue_prefers_dual_ready_over_dirty_keep_leftover():
    listed = [
        _plain("mikolaj92/Temida", 5637),
        _plain("mikolaj92/Temida", 5682),
        _dual("mikolaj92/Temida", 5714),
        _dual("mikolaj92/msds-portal", 144),
    ]
    last = {
        "leftover": 4,
        "leftover_issues": [
            {"repo": "mikolaj92/Temida", "issue": 5637},
            {"repo": "mikolaj92/Temida", "issue": 5682},
            {"repo": "mikolaj92/Temida", "issue": 5714},
            {"repo": "mikolaj92/msds-portal", "issue": 144},
        ],
    }
    out = queue(listed, last, lokay="mikolaj92")
    assert [row["issue"] for row in out] == [5714, 144]
    picked = select({"issues": listed, "count": 4}, last)
    assert picked["route"] == "ready"
    assert picked["issue"] == 5714


def test_seed_fills_ready_by_repo_from_leftover_dual_ready():
    leftover = [
        _plain("mikolaj92/Temida", 5637),
        _dual("mikolaj92/Temida", 5714),
        _dual("mikolaj92/msds-portal", 144),
        {"repo": "mikolaj92/lokay", "issue": 1071, "labels": ["ai:ready", "work:ready"]},
    ]
    working = seed_ready_from_leftover(
        {"ready_by_repo": {}, "remaining_ready": 0, "actions": []},
        leftover_issues=leftover,
    )
    assert working["remaining_ready"] >= 3
    by_repo = working["ready_by_repo"]
    assert {row["number"] for row in by_repo["mikolaj92/Temida"]} == {5714}
    assert {row["number"] for row in by_repo["mikolaj92/msds-portal"]} == {144}
    assert {row["number"] for row in by_repo["mikolaj92/lokay"]} == {1071}
    # Unlabeled dirty-keep leftover is not ready fuel.
    assert 5637 not in {row["number"] for row in by_repo["mikolaj92/Temida"]}


def test_contract_rejects_leftover_ai_ready_at_remaining_ready_zero():
    broken = {
        "leftover_issues": [_dual("mikolaj92/Temida", 5714)],
        "ready_by_repo": {},
        "remaining_ready": 0,
        "actions": [],
    }
    out = classify_leftover_ready_contract(broken)
    assert out["ok"] is False
    assert out["route"] == "contract_broken"
    assert out["reason"] == "leftover_ai_ready_remaining_ready_zero"

    filled = seed_ready_from_leftover(broken, leftover_issues=broken["leftover_issues"])
    ok = classify_leftover_ready_contract(filled)
    assert ok["ok"] is True
    assert ok["route"] == "ok"
    assert ok["remaining_ready"] >= 1

    skipped = {
        **broken,
        "ready_skip_reason": "occupied",
    }
    skip = classify_leftover_ready_contract(skipped)
    assert skip["ok"] is True
    assert skip["route"] == "skipped"
    assert skip["reason"] == "occupied"


def test_work_by_repo_unions_leftover_dual_ready():
    working = {
        "ready_by_repo": {},
        "inbox_issues_by_repo": {},
        "leftover_issues": [_dual("mikolaj92/Temida", 5714)],
        "prs_by_repo": {},
        "stuck": {"issues": {}},
    }
    work = work_by_repo(working)
    assert remaining_ready_count(work) == 1
    assert work["mikolaj92/Temida"][0]["number"] == 5714
    assert ready_by_repo_from_leftover(working["leftover_issues"])[
        "mikolaj92/Temida"
    ][0]["number"] == 5714


def test_catalog_slot_count_covers_live_repos_yaml():
    # Live mini-m4-0 catalog is 31 repos; 30-slot fail-closed blocked issue→PR.
    assert CATALOG_SLOT_COUNT >= 31
