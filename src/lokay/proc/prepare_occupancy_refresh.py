"""Prepare bounded merged, receipt, and catalog occupancy inputs."""

from lokay.passkit.working import load_begin_working
from lokay.proc.detach_issue_to_pr import (
    has_unreadable_issue_to_pr_receipts,
    live_issue_to_pr_receipts,
)


def prepare(*, pass_dir: str, slot_count: int) -> dict:
    begin, working = load_begin_working(pass_dir)
    receipts = live_issue_to_pr_receipts()
    repos = list(begin.get("repos") or [])
    if len(receipts) > slot_count or len(repos) > slot_count:
        return {
            "ok": False,
            "error": "occupancy inputs exceed authored slots",
            "receipts": len(receipts),
            "repos": len(repos),
            "slot_count": slot_count,
        }
    merged = list(
        dict.fromkeys(str(x) for x in working.get("merged_this_pass") or [] if str(x))
    )
    return {
        "ok": True,
        "merged": merged,
        "receipts": receipts,
        "repos": repos,
        "receipt_state_unknown": has_unreadable_issue_to_pr_receipts(),
    }
