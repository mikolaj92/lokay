"""Refresh the whole occupancy catalog in one atom (no 30-slot Fala unroll)."""

from __future__ import annotations

SLOTS = 30


def _one_receipt(
    prepared: dict, *, slot: int, config_path: str | None, live: bool
) -> dict:
    from lokay.proc.clear_closed_issue_receipt import clear
    from lokay.proc.inspect_live_receipt_issue import inspect
    from lokay.proc.record_live_receipt_outcome import record
    from lokay.proc.select_live_receipt_slot import select
    from lokay.proc.terminate_closed_issue_worker import terminate

    selected = select(prepared, slot=slot)
    if selected.get("route") != "receipt":
        return record(selected, {}, {}, {})
    inspected = inspect(selected, config_path=config_path, live=live)
    terminated = {}
    if inspected.get("route") == "closed":
        terminated = terminate(inspected)
    outcome = inspected
    if inspected.get("route") == "closed":
        outcome = {
            **inspected,
            "route": "terminated" if terminated.get("terminated") else "keep",
            "terminated": bool(terminated.get("terminated")),
        }
    cleared = {}
    if outcome.get("route") == "terminated":
        cleared = clear(outcome)
    return record(selected, outcome, outcome, cleared)


def _one_repo(
    prepared: dict,
    facts: dict,
    *,
    slot: int,
    pass_dir: str,
    config_path: str | None,
    live: bool,
) -> dict:
    from lokay.proc.inspect_repo_pr_refresh import inspect
    from lokay.proc.list_occupancy_pull_requests import fetch
    from lokay.proc.record_repo_pr_refresh import record
    from lokay.proc.select_occupancy_repo_slot import select

    selected = select(prepared, slot=slot)
    if selected.get("route") != "repo":
        return record(selected, {}, {})
    inspected = inspect(pass_dir=pass_dir, selected=selected, facts=facts)
    listed = {}
    if inspected.get("route") == "list":
        listed = fetch(inspected, config_path=config_path, live=live)
    return record(selected, inspected, listed)


def run(
    prepared: dict, *, pass_dir: str, config_path: str | None, live: bool
) -> dict:
    from lokay.passkit.working import load_begin_working
    from lokay.proc.clear_merged_dead_receipts import clear
    from lokay.proc.reduce_occupancy_facts import reduce_state as reduce_facts
    from lokay.proc.reduce_occupancy_refresh import reduce_state as reduce_refresh

    if not prepared.get("ok"):
        return dict(prepared)
    receipts = list(prepared.get("receipts") or [])
    repos = list(prepared.get("repos") or [])
    if len(receipts) > SLOTS or len(repos) > SLOTS:
        return {
            "ok": False,
            "error": "occupancy inputs exceed authored slots",
            "receipts": len(receipts),
            "repos": len(repos),
            "slot_count": SLOTS,
        }
    merged_clear = clear(prepared)
    receipt_rows = [
        _one_receipt(prepared, slot=slot, config_path=config_path, live=live)
        for slot in range(1, len(receipts) + 1)
    ]
    facts = reduce_facts(
        prepared=prepared, merged_clear=merged_clear, results=receipt_rows
    )
    repo_rows = [
        _one_repo(
            prepared,
            facts,
            slot=slot,
            pass_dir=pass_dir,
            config_path=config_path,
            live=live,
        )
        for slot in range(1, len(repos) + 1)
    ]
    _, working = load_begin_working(pass_dir)
    return reduce_refresh(facts=facts, results=repo_rows, working=working)
