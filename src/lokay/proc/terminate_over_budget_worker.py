"""Terminate one authoritatively reapable detached worker."""

from lokay.proc.detach_issue_to_pr import terminate_issue_to_pr_pid


def terminate(route: dict) -> dict:
    return {
        **route,
        "route": "terminated",
        "killed": bool(terminate_issue_to_pr_pid(int(route["pid"]))),
    }
