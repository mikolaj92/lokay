"""Fala bindings for one implementation-selection catalog atom (no 30-slot unroll)."""

from typing import Any

SLOT_COUNT = 30


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
    if atom == "implementation_selection_catalog":
        from lokay.proc.implementation_selection_catalog import run

        return run(
            up.get("prepare_implementation_selection") or {}, pass_dir=pass_dir
        )
    if atom == "persist_implementation_selection":
        from lokay.proc.persist_implementation_selection import persist

        return persist(
            pass_dir=pass_dir,
            reduced=up.get("implementation_selection_catalog") or {},
        )
    if atom == "summarize_implementation_selection":
        from lokay.proc.summarize_implementation_selection import summarize

        return summarize(up.get("persist_implementation_selection") or {})
    return None
