"""Fala bindings for one pass-plan catalog atom (no 30-slot unroll)."""

from typing import Any

from lokay.execution_contracts import CATALOG_SLOT_COUNT as SLOT_COUNT


def handle_pass_plan(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "")
    if atom == "prepare_pass_plan":
        from lokay.proc.prepare_pass_plan import prepare

        return prepare(pass_dir=pass_dir, slot_count=SLOT_COUNT)
    if atom == "plan_catalog":
        from lokay.proc.plan_catalog import run

        return run(up.get("prepare_pass_plan") or {}, pass_dir=pass_dir)
    if atom == "persist_pass_plan":
        from lokay.proc.persist_pass_plan import persist

        return persist(pass_dir=pass_dir, reduced=up.get("plan_catalog") or {})
    if atom == "summarize_pass_plan":
        from lokay.proc.summarize_pass_plan import summarize

        return summarize(up.get("persist_pass_plan") or {})
    return None
