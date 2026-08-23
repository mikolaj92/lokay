"""Collect a bounded, deterministic inventory for the stale-worktree subflow."""

from __future__ import annotations
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


def collect(*, pass_dir: str, config_path: str | None) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    begin, working = load_begin_working(pass_dir)
    scope = survey_scope(begin)
    receipt_unknown = has_unreadable_issue_to_pr_receipts()
    live_rows = live_issue_to_pr_receipts()
    live_keys = _live_keys(live_rows)
    live_repos = _names(working, "live_issue_to_pr_repos") | {
        repo for repo, _ in live_keys
    }
    survey_failed = _names(working, "pr_survey_failed")
    covered, heads = _covering(working, branch_prefix=cfg.branch_prefix)
    rows = []
    for repo in cfg.active_repos():
        if scope is not None and repo.name not in scope:
            continue
        for path, branch in iter_worktrees(cfg, repo):
            rows.append(
                {
                    "present": True,
                    "repo": repo.name,
                    "clone": str(repo.clone_path),
                    "path": str(path),
                    "branch": branch,
                    "issue": issue_number_from_branch(
                        branch, branch_prefix=cfg.branch_prefix
                    ),
                    "protected": (
                        "receipt_state_unknown"
                        if has_unreadable_issue_to_pr_receipts()
                        else (
                            "live_issue_to_pr"
                            if repo.name in live_repos
                            else (
                                "pr_survey_failed"
                                if repo.name in survey_failed
                                else (
                                    "covering_pr"
                                    if (
                                        issue_number_from_branch(
                                            branch, branch_prefix=cfg.branch_prefix
                                        )
                                        in covered.get(repo.name, set())
                                        or branch in heads.get(repo.name, set())
                                    )
                                    else ""
                                )
                            )
                        )
                    ),
                }
            )
    rows.sort(
        key=lambda row: (
            row["repo"],
            row["issue"] is None,
            row["issue"] or 0,
            row["branch"],
        )
    )
    slots = rows[:SLOTS]
    slots.extend({"present": False, "slot": i + 1} for i in range(len(slots), SLOTS))
    return {
        "ok": True,
        "pass_dir": pass_dir,
        "receipt_safe": not receipt_unknown,
        "candidates": slots,
        "deferred": rows[SLOTS:],
        **{f"candidate_{i+1}": row for i, row in enumerate(slots)},
    }
