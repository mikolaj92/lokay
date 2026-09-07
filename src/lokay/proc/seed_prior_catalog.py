"""Seed live occupancy and dual-ready leftover fuel into working.

Survey snapshots are not the queue. Leftover ``ai:ready`` / ``work:ready`` rows
are the takeable issue→PR fuel after the orphan survey spine was cut (#1002);
without materializing them into ``ready_by_repo``, ``remaining_ready`` stays 0
while leftover still lists dual-ready tickets (#1086).
"""

from __future__ import annotations

import os
from typing import Any

from lokay.proc.catalog_work import (
    ready_by_repo_from_leftover,
    remaining_ready_count,
    work_by_repo,
)
from lokay.proc.issue_delivery_occupancy import live_issue_to_pr_receipts


def _leftover_issues_from_last_pass() -> list[dict[str, Any]]:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return []
    from lokay.pass_receipt import read_pass_receipt

    receipt = read_pass_receipt() or {}
    remaining = receipt.get("remaining") if isinstance(receipt, dict) else None
    if not isinstance(remaining, dict):
        return []
    return [
        dict(row)
        for row in list(remaining.get("leftover_issues") or [])
        if isinstance(row, dict)
    ]


def seed_ready_from_leftover(
    working: dict[str, Any],
    *,
    leftover_issues: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Fill ``ready_by_repo`` from dual-ready leftover without wiping survey rows."""
    work = dict(working)
    rows = list(leftover_issues) if leftover_issues is not None else []
    if not rows:
        rows = [
            dict(row)
            for row in list(work.get("leftover_issues") or [])
            if isinstance(row, dict)
        ]
    if not rows:
        rows = _leftover_issues_from_last_pass()
    filled = ready_by_repo_from_leftover(rows)
    if not filled:
        return work
    existing = dict(work.get("ready_by_repo") or {})
    for repo, ready_rows in filled.items():
        have = {
            int(item.get("number", -1))
            for item in list(existing.get(repo) or [])
            if isinstance(item, dict)
        }
        merged = [
            dict(item)
            for item in list(existing.get(repo) or [])
            if isinstance(item, dict)
        ]
        for row in ready_rows:
            number = int(row.get("number", -1))
            if number < 1 or number in have:
                continue
            have.add(number)
            merged.append(row)
        existing[repo] = merged
    work["ready_by_repo"] = existing
    if rows and "leftover_issues" not in work:
        work["leftover_issues"] = rows
        work["leftover"] = len(rows)
    work["remaining_ready"] = remaining_ready_count(
        work_by_repo(work, stuck=work.get("stuck"))
    )
    return work


def seed(*, working: dict[str, Any], begin: dict[str, Any], pass_dir: str) -> dict[str, Any]:
    """Copy live issue_to_pr occupancy and dual-ready leftover into ready_by_repo."""
    del begin, pass_dir
    work = seed_ready_from_leftover(dict(working))
    live_repos = {
        str(row.get("repo") or "")
        for row in live_issue_to_pr_receipts()
        if str(row.get("repo") or "")
    }
    if live_repos:
        occupied = {
            str(name) for name in list(work.get("occupied_repos") or []) if name
        }
        live = {
            str(name) for name in list(work.get("live_issue_to_pr_repos") or []) if name
        }
        work["occupied_repos"] = sorted(occupied | live_repos)
        work["live_issue_to_pr_repos"] = sorted(live | live_repos)
    return work
