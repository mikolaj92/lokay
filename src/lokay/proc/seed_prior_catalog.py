"""Seed live occupancy only. Survey snapshots are not the queue."""

from __future__ import annotations

from typing import Any

from lokay.proc.issue_delivery_occupancy import live_issue_to_pr_receipts


def seed(*, working: dict[str, Any], begin: dict[str, Any], pass_dir: str) -> dict[str, Any]:
    """Copy live issue_to_pr occupancy. Do not replay prior survey catalogs."""
    del begin, pass_dir
    work = dict(working)
    live_repos = {
        str(row.get("repo") or "")
        for row in live_issue_to_pr_receipts()
        if str(row.get("repo") or "")
    }
    if live_repos:
        occupied = {str(name) for name in list(work.get("occupied_repos") or []) if name}
        live = {str(name) for name in list(work.get("live_issue_to_pr_repos") or []) if name}
        work["occupied_repos"] = sorted(occupied | live_repos)
        work["live_issue_to_pr_repos"] = sorted(live | live_repos)
    return work
