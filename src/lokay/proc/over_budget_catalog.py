"""Reap the whole over-budget catalog in one atom (no 723-slot Fala unroll)."""

from __future__ import annotations

SLOTS = 30


def _stable(primary: dict, fallback: dict) -> dict:
    return dict(primary if primary.get("ok") else fallback)


def _one_slot(
    prepared: dict,
    *,
    slot: int,
    config_path: str | None,
    live: bool,
    budget_s: int,
) -> dict:
    from lokay.proc.check_receipt_budget import check
    from lokay.proc.commit_over_budget_diff import commit
    from lokay.proc.create_over_budget_pr import create
    from lokay.proc.inspect_budget_coder import inspect as inspect_coder
    from lokay.proc.inspect_budget_coder_diff import inspect as inspect_diff
    from lokay.proc.inspect_budget_issue_state import inspect as inspect_issue
    from lokay.proc.park_plan_only_issue import park
    from lokay.proc.push_over_budget_branch import push
    from lokay.proc.record_budget_slot_outcome import record
    from lokay.proc.record_plan_only_failure import record as record_failure
    from lokay.proc.select_budget_harvest_outcome import select as select_harvest
    from lokay.proc.select_budget_receipt_route import select as select_route
    from lokay.proc.select_budget_receipt_slot import select
    from lokay.proc.stamp_reaped_receipt import stamp
    from lokay.proc.terminate_over_budget_worker import terminate

    selected = select(prepared, slot=slot)
    if selected.get("route") != "receipt":
        return record(selected, {}, {}, {}, {}, {})
    inspected = inspect_issue(selected, config_path=config_path, live=live)
    issue = (
        {**inspected, "route": "check"}
        if selected.get("route") == "receipt"
        else dict(selected)
    )
    checked = {}
    if issue.get("route") == "check":
        checked = check(selected, issue, budget_s=budget_s)
    checked = _stable(checked, selected)
    coder = {}
    if checked.get("route") == "inspect_coder":
        coder = inspect_coder(checked)
    coder = _stable(coder, checked)
    diff = {}
    if coder.get("route") == "diff":
        diff = inspect_diff(coder)
    diff = _stable(diff, coder)
    route = select_route(selected, issue, checked, coder, diff)
    committed = {}
    if route.get("route") == "harvest":
        committed = commit(route, config_path=config_path, live=live)
    committed = _stable(committed, route)
    pushed = {}
    if committed.get("route") == "committed":
        pushed = push(committed, config_path=config_path, live=live)
    pushed = _stable(pushed, committed)
    created = {}
    if pushed.get("route") == "pushed":
        created = create(pushed, config_path=config_path, live=live)
    harvest = select_harvest(route, committed, pushed, created)
    terminated = {}
    if harvest.get("route") == "reap":
        terminated = terminate(harvest)
    terminated = _stable(terminated, harvest)
    stamped = {}
    if terminated.get("route") == "terminated":
        stamped = stamp(terminated)
    stamped = _stable(stamped, terminated)
    stamped = {**stamped, "reason": str(stamped.get("reason") or "none")}
    recorded = {}
    if stamped.get("reason") == "over_budget":
        recorded = record_failure(
            stamped, stuck_path=str(prepared["stuck_path"])
        )
    recorded = _stable(recorded, stamped)
    parked = {}
    if recorded.get("route") == "park":
        parked = park(recorded, config_path=config_path, live=live)
    return record(selected, route, harvest, terminated, stamped, parked)


def run(
    prepared: dict,
    *,
    config_path: str | None,
    live: bool,
    budget_s: int,
) -> dict:
    from lokay.proc.reduce_over_budget_reap import reduce_state

    if not prepared.get("ok"):
        return dict(prepared)
    rows = [
        _one_slot(
            prepared,
            slot=slot,
            config_path=config_path,
            live=live,
            budget_s=budget_s,
        )
        for slot in range(1, SLOTS + 1)
    ]
    return reduce_state(rows=rows, budget_s=budget_s)
