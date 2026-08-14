"""When is an in-flight ledger stage abandoned? Pure — no gh/git."""

from __future__ import annotations

from typing import Any

from lokay.stuck import issue_number_from_branch, issue_numbers_covered_by_prs


def should_reap_abandoned(*, has_live_job: bool, has_covering_pr: bool) -> bool:
    """True when implementing/pr-open has no live job and no covering open PR."""
    return (not has_live_job) and (not has_covering_pr)


def should_reap_implementing(*, has_live_job: bool, has_covering_pr: bool) -> bool:
    """True when the ledger says implementing but nothing is actually in flight."""
    return should_reap_abandoned(
        has_live_job=has_live_job, has_covering_pr=has_covering_pr
    )


def should_reap_pr_open(*, has_live_job: bool, has_covering_pr: bool) -> bool:
    """True when the ledger says pr-open but no open covering PR remains."""
    return should_reap_abandoned(
        has_live_job=has_live_job, has_covering_pr=has_covering_pr
    )


def issue_has_covering_pr(
    number: int, prs: list[dict[str, Any]], *, branch_prefix: str = "ai/fix"
) -> bool:
    covered = issue_numbers_covered_by_prs(prs, branch_prefix=branch_prefix)
    if int(number) in covered:
        return True
    needle = f"#{int(number)}"
    for pr in prs:
        if not isinstance(pr, dict):
            continue
        title = str(pr.get("title") or "")
        if needle in title:
            return True
        n = issue_number_from_branch(
            str(pr.get("head_ref") or ""), branch_prefix=branch_prefix
        )
        if n == int(number):
            return True
    return False
