"""Clear dead detached receipts for repositories merged this pass."""

from lokay.proc.detach_issue_to_pr import clear_dead_issue_to_pr_receipts


def clear(prepared: dict) -> dict:
    return {
        "ok": True,
        "cleared": clear_dead_issue_to_pr_receipts(list(prepared.get("merged") or [])),
    }
