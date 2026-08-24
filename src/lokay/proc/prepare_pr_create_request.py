"""Normalize one exact pull-request publication request."""

import re

from lokay.stuck import issue_number_from_branch


def prepare(
    *,
    repo: str,
    issue: int | None,
    title: str,
    body: str,
    head: str,
    base: str,
    branch_prefix: str,
    live: bool,
) -> dict:
    head_issue = issue_number_from_branch(head, branch_prefix=branch_prefix)
    number = head_issue if head_issue is not None else issue
    if head_issue is not None and issue is not None and head_issue != issue:
        body = re.sub(
            rf"(\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+)#{issue}\b",
            rf"\g<1>#{head_issue}",
            body,
            flags=re.IGNORECASE,
        )
    if number is not None:
        body = f"{body}\nFixes #{number}" if body else f"Fixes #{number}"
    return {
        "ok": True,
        "repo": repo,
        "issue": number,
        "title": title,
        "body": body,
        "head": head,
        "base": base,
        "live": live,
    }
