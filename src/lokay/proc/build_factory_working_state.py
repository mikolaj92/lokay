"""Purely build one empty mutable factory working ledger."""


def build(ledger: dict) -> dict:
    zeros = (
        "progress",
        "blocked_this_pass",
        "pending_checks",
        "no_checks_blocked",
        "merge_conflicts",
        "needs_repair",
        "mergeable_green",
        "merge_disabled",
        "review_limbo",
        "remaining_inbox",
        "remaining_ready",
        "remaining_ready_with_pr",
        "remaining_prs",
        "actionable_prs",
        "manual_prs",
        "survey_errors",
        "issue_to_pr_started",
    )
    working = {key: 0 for key in zeros}
    working.update(
        actions=[],
        intake_skip_reason=None,
        merged_this_pass=[],
        occupied_repos=[],
        live_issue_to_pr_repos=[],
        prs_by_repo={},
        inbox_by_repo={},
        ready_by_repo={},
        pr_survey_failed=[],
        inbox_survey_failed=[],
        ready_survey_failed=[],
        stuck=ledger["stuck"],
    )
    return {"ok": True, "working": working}
