"""Repair stale blocked miss counts from journal run identity."""

from lokay.child_harvest import (
    MISS_REASONS,
    _apply_miss_count,
    _as_int,
    _trailing_miss_runs,
)


def reconcile(facts: dict) -> dict:
    stuck = dict(facts.get("stuck") or {})
    history = facts.get("history") or {}
    for key, row in list((stuck.get("issues") or {}).items()):
        if (
            not isinstance(row, dict)
            or not row.get("blocked")
            or str(row.get("reason") or "") not in MISS_REASONS
        ):
            continue
        repo, sep, num = key.rpartition("#")
        issue = _as_int(num)
        if not sep or not repo or issue is None:
            continue
        reason, runs = _trailing_miss_runs(history.get(key) or [])
        if runs:
            _apply_miss_count(
                stuck,
                repo=repo,
                issue=issue,
                reason=reason or str(row.get("reason")),
                miss_runs=runs,
                error=str(row.get("last_error") or reason or row.get("reason")),
            )
    return {**facts, "stuck": stuck}
