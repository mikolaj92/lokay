"""Collect a bounded inventory for the stale-worktree child (worktrees only)."""

from __future__ import annotations
from pathlib import Path
from lokay.passkit.hot import survey_scope
from lokay.passkit.working import load_begin_working
from lokay.git_worktree import iter_worktrees
from lokay.proc._common import load_cfg
from lokay.proc.detach_issue_to_pr import (
    has_unreadable_issue_to_pr_receipts,
    live_issue_to_pr_receipts,
)
from lokay.proc.reap_stale_worktrees import _covering, _live_keys, _names
from lokay.stuck import issue_number_from_branch
import argparse

SLOTS = 4


def protection(
    *,
    repo: str,
    branch: str,
    issue: int | None,
    receipt_unknown: bool,
    live_keys: set[tuple[str, int]],
    survey_failed: set[str],
    covered: dict[str, set[int]],
    heads: dict[str, set[str]],
) -> str:
    """One job: KEEP reason for a live/unknown/covering corner, else empty.

    Live i2pr KEEP is issue-scoped (repo+issue), never whole-repo.
    """
    if receipt_unknown:
        return "receipt_state_unknown"
    if issue is not None and (repo, issue) in live_keys:
        return "live_issue_to_pr"
    if repo in survey_failed:
        return "pr_survey_failed"
    if issue in covered.get(repo, set()) or branch in heads.get(repo, set()):
        return "covering_pr"
    return ""


def _row_mtime(row: dict) -> float:
    try:
        return Path(str(row["path"])).stat().st_mtime
    except (OSError, KeyError, TypeError, ValueError):
        return float("inf")


def bound_slots(
    rows: list[dict], *, pass_dir: str, receipt_safe: bool
) -> dict:
    """One job: oldest-first authored slots; defer remainder for a later pass."""
    rows = sorted(
        rows,
        key=lambda row: (
            _row_mtime(row),
            row["repo"],
            row["issue"] is None,
            row["issue"] or 0,
            row["branch"],
        ),
    )
    slots = rows[:SLOTS]
    slots.extend({"present": False, "slot": i + 1} for i in range(len(slots), SLOTS))
    return {
        "ok": True,
        "pass_dir": pass_dir,
        "receipt_safe": receipt_safe,
        "candidates": slots,
        "deferred": rows[SLOTS:],
        **{f"candidate_{i + 1}": row for i, row in enumerate(slots)},
    }


def collect(*, pass_dir: str, config_path: str | None) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    begin, working = load_begin_working(pass_dir)
    scope = survey_scope(begin)
    receipt_unknown = has_unreadable_issue_to_pr_receipts()
    live_keys = _live_keys(live_issue_to_pr_receipts())
    # live_issue_to_pr_repos is advisory occupancy only — KEEP uses live_keys.
    survey_failed = _names(working, "pr_survey_failed")
    covered, heads = _covering(working, branch_prefix=cfg.branch_prefix)
    rows = []
    for repo in cfg.active_repos():
        if scope is not None and repo.name not in scope:
            continue
        for path, branch in iter_worktrees(cfg, repo):
            issue = issue_number_from_branch(branch, branch_prefix=cfg.branch_prefix)
            rows.append(
                {
                    "present": True,
                    "repo": repo.name,
                    "clone": str(repo.clone_path),
                    "path": str(path),
                    "branch": branch,
                    "issue": issue,
                    "protected": protection(
                        repo=repo.name,
                        branch=branch,
                        issue=issue,
                        receipt_unknown=receipt_unknown,
                        live_keys=live_keys,
                        survey_failed=survey_failed,
                        covered=covered,
                        heads=heads,
                    ),
                }
            )
    return bound_slots(
        rows, pass_dir=pass_dir, receipt_safe=not receipt_unknown
    )
