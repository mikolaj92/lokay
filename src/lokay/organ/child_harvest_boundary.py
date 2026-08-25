"""Fala bindings for one authored detached-child harvest."""

from typing import Any


def handle_child_harvest(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    previous = {
        "reconcile_dead_child_receipts": "collect_child_harvest_facts",
        "reconcile_harvest_journal_misses": "reconcile_dead_child_receipts",
        "reconcile_harvest_deliveries": "reconcile_harvest_journal_misses",
        "reconcile_harvest_blocked_misses": "reconcile_harvest_deliveries",
        "harvest_catalog": "reconcile_harvest_blocked_misses",
        "clear_harvest_closed_rows": "harvest_catalog",
        "drop_harvest_out_of_scope": "clear_harvest_closed_rows",
        "clear_harvest_cycle_starts": "drop_harvest_out_of_scope",
        "child_harvest_terminal": "clear_harvest_cycle_starts",
    }
    if atom == "collect_child_harvest_facts":
        from lokay.proc.collect_child_harvest_facts import collect

        return collect(
            dict(inputs.get("harvest_config") or {}),
            dict(inputs.get("harvest_scope") or {}),
            dict(inputs.get("harvest_ledger") or {}),
        )
    facts = up.get(previous.get(atom, "")) or {}
    if atom == "reconcile_dead_child_receipts":
        from lokay.proc.reconcile_dead_child_receipts import reconcile

        return reconcile(facts)
    if atom == "reconcile_harvest_journal_misses":
        from lokay.proc.reconcile_harvest_journal_misses import reconcile

        return reconcile(facts)
    if atom == "reconcile_harvest_deliveries":
        from lokay.proc.reconcile_harvest_deliveries import reconcile

        return reconcile(facts)
    if atom == "reconcile_harvest_blocked_misses":
        from lokay.proc.reconcile_harvest_blocked_misses import reconcile

        return reconcile(facts)
    if atom == "harvest_catalog":
        from lokay.proc.harvest_catalog import harvest

        return harvest(facts)
    if atom == "clear_harvest_closed_rows":
        from lokay.proc.clear_harvest_closed_rows import clear

        return clear(facts)
    if atom == "drop_harvest_out_of_scope":
        from lokay.proc.drop_harvest_out_of_scope import drop

        return drop(facts)
    if atom == "clear_harvest_cycle_starts":
        from lokay.proc.clear_harvest_cycle_starts import clear

        return clear(facts)
    if atom == "child_harvest_terminal":
        from lokay.proc.child_harvest_terminal import terminal

        return terminal(facts)
    return None
