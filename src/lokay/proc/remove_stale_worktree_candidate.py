"""Remove one fully classified stale worktree, with a live-receipt recheck."""

from pathlib import Path
from lokay.git_worktree import remove_worktree
from lokay.proc._common import load_cfg, mutations_allowed, runner
from lokay.proc.detach_issue_to_pr import (
    has_unreadable_issue_to_pr_receipts,
    live_issue_to_pr_receipts,
)
import argparse


def apply(classified: dict, *, config_path: str | None, live: bool) -> dict:
    row = dict(classified.get("row") or {})
    repo = str(row.get("repo") or "")
    issue = row.get("issue")
    occupied = {
        (str(x.get("repo") or ""), int(x.get("issue") or 0))
        for x in live_issue_to_pr_receipts()
    }
    if has_unreadable_issue_to_pr_receipts() or (repo, int(issue or 0)) in occupied:
        return {
            "ok": True,
            "applied": False,
            "row": {**row, "kept": True, "reason": "live_issue_to_pr"},
        }
    cfg = load_cfg(argparse.Namespace(config=config_path))
    mutations_allowed(live_flag=live, cfg=cfg)
    out = remove_worktree(
        runner(),
        Path(str(row["clone"])),
        Path(str(row["path"])),
        managed_root=cfg.worktrees_root,
    )
    if not out.get("ok"):
        return {
            "ok": True,
            "applied": False,
            "row": {
                **row,
                "kept": True,
                "reason": "remove_failed",
                "error": out.get("error"),
            },
        }
    return {"ok": True, "applied": True, "row": {**row, "kept": False, "removed": True}}
