"""Terminate one authoritatively reapable detached worker."""

from lokay.proc.detach_issue_to_pr import (
    terminate_issue_to_pr_pid,
    terminate_orphan_coders_for_issue,
)


def terminate(route: dict) -> dict:
    wrapper = bool(terminate_issue_to_pr_pid(int(route["pid"])))
    orphans = False
    try:
        issue = int(route.get("issue") or 0)
    except (TypeError, ValueError):
        issue = 0
    if issue > 0:
        orphans = bool(terminate_orphan_coders_for_issue(issue))
    return {
        **route,
        "route": "terminated",
        "killed": wrapper or orphans,
    }
