"""Clear one terminated closed-issue receipt by exact identity."""

from lokay.proc.detach_issue_to_pr import clear_issue_to_pr_receipt


def clear(terminated: dict) -> dict:
    return {
        "ok": True,
        "cleared": bool(clear_issue_to_pr_receipt(dict(terminated["receipt"]))),
        **terminated,
    }
