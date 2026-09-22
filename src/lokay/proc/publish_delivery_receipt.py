"""Observe merged delivery and replace the provisional PR receipt marker."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from lokay.delivery_receipt import PATTERN, finalize_receipt, marker, parse_marker


def publish_from_config(
    *, config_path: str | None, repo: str, pr: int, issue: int,
    merge: dict, close: dict, live: bool, review: dict | None = None,
    tests: dict | None = None, closeout_intent: dict | None = None,
) -> dict[str, Any]:
    """Shared external adapter for first-pass publication and durable replay."""
    from lokay.config import load_config
    from lokay.gh_prs import gh_json, gh_text
    from lokay.proc import pr_repair_receipts as receipts
    from lokay.proc._common import mutations_allowed, runner

    if not live:
        return {"ok": True, "route": "planned", "confirmed": False, "planned": True}
    cfg = load_config(config_path)
    carrier = runner(cfg)

    def read_pr(observed_repo: str, observed_pr: int) -> dict[str, Any]:
        return gh_json(carrier, [
            "pr", "view", str(observed_pr), "--repo", observed_repo, "--json",
            "body,headRefOid,headRefName,headRepository,baseRefName,state,mergeCommit,mergedAt",
        ], live=live)

    def read_issue(observed_repo: str, observed_issue: int) -> dict[str, Any]:
        return gh_json(carrier, [
            "issue", "view", str(observed_issue), "--repo", observed_repo, "--json", "state",
        ], live=live)

    def main_contains(observed_repo: str, head: str) -> bool:
        return gh_text(carrier, [
            "api", f"repos/{observed_repo}/compare/{head}...main", "--jq", ".status",
        ], live=live, require_success=True).strip() in {"ahead", "identical"}

    def edit_pr(observed_repo: str, observed_pr: int, body: str) -> str:
        if not mutations_allowed(live_flag=live, cfg=cfg):
            raise ValueError("delivery receipt mutation not authorized")
        return gh_text(carrier, [
            "pr", "edit", str(observed_pr), "--repo", observed_repo, "--body", body,
        ], live=live, require_success=True)

    state_path = getattr(cfg, "state_path", None)
    try:
        repair_receipt = receipts.read(
            repo, pr, state_dir=state_path.expanduser().resolve().parent,
        ) if state_path else {}
        return publish(
            repo=repo, pr=pr, issue=issue, merge=merge, close=close, live=live,
            read_pr=read_pr, read_issue=read_issue, main_contains=main_contains,
            edit_pr=edit_pr, repair_receipt=repair_receipt, review=review, tests=tests,
            closeout_intent=closeout_intent,
        )
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        return {"ok": True, "route": "pending", "confirmed": False,
                "reason": "delivery_publication_failed", "detail": str(exc)}


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
    closeout_intent: dict | None = None,
) -> dict[str, Any]:
    """Publish only after authoritative reads confirm the complete delivery."""
    if not live:
        return {"ok": True, "route": "planned", "confirmed": False, "planned": True}
    if not merge.get("merged"):
        return {"ok": True, "route": "pending", "confirmed": False, "reason": "merge_unconfirmed"}

    viewed = read_pr(repo, pr)
    if closeout_intent is not None:
        from lokay.proc.delivery_closeout import validate

        intent = validate(closeout_intent)
        if ((intent['repo'], intent['pr'], intent['issue']) != (repo, pr, issue)
                or viewed.get('headRefOid') != intent['head_sha']
                or viewed.get('headRefName') != intent['branch']
                or (viewed.get('headRepository') or {}).get('nameWithOwner') != repo
                or viewed.get('baseRefName') != 'main' or viewed.get('state') != 'MERGED'):
            return {'ok': True, 'route': 'pending', 'confirmed': False,
                    'reason': 'delivery_closeout_identity_mismatch'}
    body = str(viewed.get("body") or "")
    provisional = parse_marker(body)
    if provisional is None:
        return {"ok": True, "route": "pending", "confirmed": False, "reason": "receipt_missing"}

    head = str(viewed.get("headRefOid") or "")
    if any(provisional.get(key) != value for key, value in (("repo", repo), ("issue", issue))):
        return {"ok": True, "route": "pending", "confirmed": False, "reason": "receipt_identity_mismatch"}
    if provisional.get("head_sha") != head or review or tests:
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

    try:
        complete = finalize_receipt(
            provisional,
            merge_sha=merge_sha,
            merged_at=merged_at,
            issue_closed=issue_closed,
            main_contains_head=on_main,
        )
    except ValueError as exc:
        return {"ok": True, "route": "pending", "confirmed": False,
                "reason": str(exc), "issue_closed": issue_closed}
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
