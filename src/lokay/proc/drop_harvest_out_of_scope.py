"""Drop only stuck rows outside the explicit configured catalog."""

from lokay.child_harvest import _drop_out_of_scope_stuck_rows


def drop(facts: dict) -> dict:
    stuck = dict(facts.get("stuck") or {})
    _drop_out_of_scope_stuck_rows(stuck, list(facts.get("repos") or []))
    return {**facts, "stuck": stuck}
