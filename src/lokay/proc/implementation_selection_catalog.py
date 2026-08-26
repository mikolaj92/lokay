"""Classify the whole implementation catalog in one atom (no 30-slot Fala unroll)."""

from __future__ import annotations


def _one_slot(prepared: dict, *, pass_dir: str, slot: int) -> dict:
    from lokay.proc.inspect_implementation_eligibility import inspect
    from lokay.proc.record_eligible_implementation_repo import record as record_eligible
    from lokay.proc.record_ineligible_implementation_repo import (
        record as record_ineligible,
    )
    from lokay.proc.select_implementation_eligibility_gate import select as select_gate
    from lokay.proc.select_implementation_repo_slot import select
    from lokay.proc.select_implementation_slot_outcome import select as select_outcome

    selected = select(prepared, slot=slot)
    inspected = {}
    if selected.get("route") == "repo":
        inspected = inspect(
            pass_dir=pass_dir, prepared=prepared, selected=selected
        )
    gated = select_gate(selected, inspected)
    eligible = {}
    if gated.get("route") == "eligible":
        eligible = record_eligible(gated)
    ineligible = record_ineligible(selected, inspected)
    return select_outcome(selected, eligible, ineligible)


def run(prepared: dict, *, pass_dir: str) -> dict:
    from lokay.passkit import io as pass_io
    from lokay.proc.reduce_implementation_selection import reduce_state

    if not prepared.get("ok"):
        return dict(prepared)
    repos = list(prepared.get("repos") or [])
    results = [
        _one_slot(prepared, pass_dir=pass_dir, slot=slot)
        for slot in range(1, len(repos) + 1)
    ]
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    return reduce_state(prepared=prepared, results=results, working=working)
