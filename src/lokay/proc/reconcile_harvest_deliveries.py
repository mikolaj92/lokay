"""Clear stale no-PR rows with durable delivery evidence."""

from lokay.child_harvest import _clear_stale_no_pr, _event_delivered


def reconcile(facts: dict) -> dict:
    stuck = dict(facts.get("stuck") or {})
    for key, event in (facts.get("events") or {}).items():
        if _event_delivered(event):
            repo, _, num = key.rpartition("#")
            _clear_stale_no_pr(stuck, repo, int(num))
    return {**facts, "stuck": stuck}
