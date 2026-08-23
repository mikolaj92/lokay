"""Fala bindings for explicit implementation-repository slots."""

from typing import Any

SLOT_COUNT = 30


def _slot(atom: str) -> int:
    return int(atom.rsplit("_", 1)[1])


def handle_implementation_selection(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "")
    if atom == "prepare_implementation_selection":
        from lokay.proc.prepare_implementation_selection import prepare

        return prepare(pass_dir=pass_dir, slot_count=SLOT_COUNT)
    slot = _slot(atom) if atom.rsplit("_", 1)[-1].isdigit() else 0
    if atom.startswith("select_implementation_repo_"):
        from lokay.proc.select_implementation_repo_slot import select

        return select(up.get("prepare_implementation_selection") or {}, slot=slot)
    if atom.startswith("inspect_implementation_eligibility_"):
        from lokay.proc.inspect_implementation_eligibility import inspect

        return inspect(
            pass_dir=pass_dir,
            prepared=up.get("prepare_implementation_selection") or {},
            selected=up.get(f"select_implementation_repo_{slot}") or {},
        )
    if atom.startswith("select_implementation_eligibility_gate_"):
        from lokay.proc.select_implementation_eligibility_gate import select

        return select(
            up.get(f"select_implementation_repo_{slot}") or {},
            up.get(f"inspect_implementation_eligibility_{slot}") or {},
        )
    if atom.startswith("record_eligible_implementation_repo_"):
        from lokay.proc.record_eligible_implementation_repo import record

        return record(up.get(f"select_implementation_eligibility_gate_{slot}") or {})
    if atom.startswith("record_ineligible_implementation_repo_"):
        from lokay.proc.record_ineligible_implementation_repo import record

        return record(
            up.get(f"select_implementation_repo_{slot}") or {},
            up.get(f"inspect_implementation_eligibility_{slot}") or {},
        )
    if atom.startswith("select_implementation_slot_outcome_"):
        from lokay.proc.select_implementation_slot_outcome import select

        return select(
            up.get(f"select_implementation_repo_{slot}") or {},
            up.get(f"record_eligible_implementation_repo_{slot}") or {},
            up.get(f"record_ineligible_implementation_repo_{slot}") or {},
        )
    if atom == "reduce_implementation_selection":
        from lokay.passkit import io as pass_io
        from lokay.proc.reduce_implementation_selection import reduce_state

        working = pass_io.read_json(pass_io.working_path(pass_dir))
        results = [
            up.get(f"select_implementation_slot_outcome_{i}") or {}
            for i in range(1, SLOT_COUNT + 1)
        ]
        return reduce_state(
            prepared=up.get("prepare_implementation_selection") or {},
            results=results,
            working=working,
        )
    if atom == "persist_implementation_selection":
        from lokay.proc.persist_implementation_selection import persist

        return persist(
            pass_dir=pass_dir, reduced=up.get("reduce_implementation_selection") or {}
        )
    if atom == "summarize_implementation_selection":
        from lokay.proc.summarize_implementation_selection import summarize

        return summarize(up.get("persist_implementation_selection") or {})
    return None
