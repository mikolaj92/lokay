"""Reconcile terminal plan-only evidence retained only in the journal."""

from lokay.child_harvest import _apply_miss_count, _skip_after, _trailing_miss_runs


def reconcile(facts: dict) -> dict:
    stuck = dict(facts.get("stuck") or {})
    events = facts.get("events") or {}
    for key, hist in (facts.get("history") or {}).items():
        reason, runs = _trailing_miss_runs(hist)
        if reason != "plan_only" or runs < _skip_after(reason):
            continue
        repo, _, num = key.rpartition("#")
        ev = events.get(key) or {}
        _apply_miss_count(
            stuck,
            repo=repo,
            issue=int(num),
            reason=reason,
            miss_runs=runs,
            error=str(ev.get("error") or ev.get("reason") or reason),
        )
    return {**facts, "stuck": stuck}
