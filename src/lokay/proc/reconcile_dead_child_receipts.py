"""Reconcile only dead detached-child receipts into the stuck ledger."""

from pathlib import Path

from lokay.child_harvest import (
    FAIL_CLOSED,
    MISS_REASONS,
    _apply_miss_count,
    _as_int,
    _classify,
    _clear_stale_no_pr,
    _event_delivered,
    _event_from_fala_journal,
    _trailing_miss_runs,
)
from lokay.proc.detach_issue_to_pr import is_live_issue_to_pr_pid
from lokay.stuck import is_blocked_in_ledger, record_failure


def reconcile(facts: dict) -> dict:
    stuck = dict(facts.get("stuck") or {})
    events = facts.get("events") or {}
    history = facts.get("history") or {}
    home = Path(facts["home"])
    for data in facts.get("receipts") or []:
        repo = str(data.get("repo") or "")
        issue = _as_int(data.get("issue"))
        pid = _as_int(data.get("pid"))
        if (
            not repo
            or issue is None
            or "pid" not in data
            or (pid is not None and is_live_issue_to_pr_pid(pid))
        ):
            continue
        key = f"{repo}#{issue}"
        event = events.get(key)
        reason = _classify(event)
        if not reason:
            fallback = _event_from_fala_journal(repo, issue, home)
            if fallback is not None:
                event = fallback
                reason = _classify(event)
        if (
            not reason
            and isinstance(data.get("reason"), str)
            and data["reason"] in FAIL_CLOSED
        ):
            reason = data["reason"]
            event = event or {"ok": False, "reason": reason}
        if not reason:
            if (
                _as_int(data.get("pr"))
                or _as_int((event or {}).get("pr"))
                or _event_delivered(event)
            ):
                _clear_stale_no_pr(stuck, repo, issue)
                continue
            if event is not None:
                continue
            reason = "no_pr"
            event = {
                "ok": False,
                "reason": "no_pr",
                "error": "issue_to_pr produced no PR",
            }
        error = str((event or {}).get("error") or (event or {}).get("reason") or reason)
        if reason in FAIL_CLOSED:
            if is_blocked_in_ledger(stuck, repo, issue):
                continue
            row = record_failure(
                stuck, repo=repo, number=issue, error=error or reason, max_failures=1
            )
            row.update(blocked=True, reason=reason)
            continue
        if reason not in MISS_REASONS:
            continue
        miss_reason, miss_runs = _trailing_miss_runs(history.get(key) or [])
        counted = miss_reason or reason
        if miss_runs == 0:
            miss_runs = 1
            counted = reason
        _apply_miss_count(
            stuck,
            repo=repo,
            issue=issue,
            reason=counted,
            miss_runs=miss_runs,
            error=error or counted,
        )
    return {**facts, "stuck": stuck}
