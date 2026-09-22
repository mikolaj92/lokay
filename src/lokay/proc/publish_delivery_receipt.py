"""Observe merged delivery and replace the provisional PR receipt marker."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from lokay.delivery_receipt import PATTERN, finalize_receipt, marker, parse_marker


def publish(
    *,
    repo: str,
    pr: int,
    issue: int,
    merge: dict,
    close: dict,
    live: bool,
    read_pr: Callable[[str, int], dict[str, Any]],
    read_issue: Callable[[str, int], dict[str, Any]],
    main_contains: Callable[[str, str], bool],
    edit_pr: Callable[[str, int, str], Any],
    repair_receipt: dict | None = None,
    review: dict | None = None,
    tests: dict | None = None,
) -> dict[str, Any]:
    """Publish only after authoritative reads confirm the complete delivery."""
    if not live:
        return {"ok": True, "route": "planned", "confirmed": False, "planned": True}
    if not merge.get("merged"):
        return {"ok": True, "route": "pending", "confirmed": False, "reason": "merge_unconfirmed"}

    viewed = read_pr(repo, pr)
    body = str(viewed.get("body") or "")
    provisional = parse_marker(body)
    if provisional is None:
        return {"ok": True, "route": "pending", "confirmed": False, "reason": "receipt_missing"}

    head = str(viewed.get("headRefOid") or "")
    if any(provisional.get(key) != value for key, value in (("repo", repo), ("issue", issue))):
        return {"ok": True, "route": "pending", "confirmed": False, "reason": "receipt_identity_mismatch"}
    if provisional.get("head_sha") != head:
        from lokay.proc.delivery_lineage import advance
        try:
            provisional = advance(provisional, repo=repo, pr=pr, issue=issue, viewed=viewed,
                                  repair_receipt=repair_receipt or {}, review=review or {}, tests=tests or {})
        except (ValueError, KeyError, TypeError) as exc:
            reason = str(exc) if str(exc).startswith("receipt_") else "receipt_repair_lineage_unverified"
            if not review and not tests:
                reason = "receipt_identity_mismatch"
            return {"ok": True, "route": "pending", "confirmed": False, "reason": reason}
    merge_sha = str((viewed.get("mergeCommit") or {}).get("oid") or "")
    merged_at = str(viewed.get("mergedAt") or "")
    issue_closed = str(read_issue(repo, issue).get("state") or "").upper() == "CLOSED"
    on_main = bool(head and main_contains(repo, head))
    if not (head and merge_sha and merged_at and issue_closed and on_main):
        return {
            "ok": True,
            "route": "pending",
            "confirmed": False,
            "reason": "delivery_confirmation_incomplete",
            "issue_closed": issue_closed,
        }

    complete = finalize_receipt(
        provisional,
        merge_sha=merge_sha,
        merged_at=merged_at,
        issue_closed=issue_closed,
        main_contains_head=on_main,
    )
    final_body = PATTERN.sub(lambda _match: marker(complete), body, count=1)
    if final_body != body:
        edit_pr(repo, pr, final_body)
    return {
        "ok": True,
        "route": "confirmed",
        "confirmed": True,
        "repo": repo,
        "pr": pr,
        "issue": issue,
        "issue_closed": issue_closed,
        "body": final_body,
        "receipt": complete,
    }
