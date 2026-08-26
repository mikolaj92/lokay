"""Cheap inbox / occupancy fact: copy the newest prior catalog into this pass."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lokay.passkit import io as pass_io
from lokay.proc.issue_delivery_occupancy import live_issue_to_pr_receipts

_CATALOG_KEYS = (
    "prs_by_repo",
    "inbox_by_repo",
    "inbox_issues_by_repo",
    "ready_by_repo",
    "occupied_repos",
    "live_issue_to_pr_repos",
    "merged_this_pass",
    "pr_survey_failed",
    "inbox_survey_failed",
    "ready_survey_failed",
    "remaining_inbox",
    "remaining_ready",
    "remaining_ready_with_pr",
    "remaining_prs",
    "actionable_prs",
    "manual_prs",
)


def _has_catalog(work: dict[str, Any]) -> bool:
    return bool(
        work.get("ready_by_repo")
        or work.get("inbox_issues_by_repo")
        or work.get("prs_by_repo")
    )


def _prior_working(state_path: str, current: Path) -> dict[str, Any] | None:
    root = Path(state_path).expanduser().resolve().parent
    try:
        dirs = [path for path in root.glob("factory-pass-*") if path.is_dir()]
    except OSError:
        return None
    try:
        current_res = current.expanduser().resolve()
    except OSError:
        current_res = current
    dirs.sort(
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    for path in dirs:
        try:
            if path.resolve() == current_res:
                continue
        except OSError:
            if path == current:
                continue
        try:
            work = pass_io.read_json(path / "working.json")
        except (OSError, ValueError):
            continue
        if _has_catalog(work):
            return work
    return None


def seed(*, working: dict[str, Any], begin: dict[str, Any], pass_dir: str) -> dict[str, Any]:
    """Merge prior catalog rows and live occupancy into this pass ledger."""
    work = dict(working)
    state_path = str(begin.get("state_path") or "")
    if state_path:
        prior = _prior_working(state_path, Path(pass_dir))
        if prior is not None:
            for key in _CATALOG_KEYS:
                if key in prior:
                    work[key] = prior[key]
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
