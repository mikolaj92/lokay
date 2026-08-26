"""Fala bindings for one over-budget catalog atom (no 723-slot unroll)."""

from typing import Any


def handle_over_budget(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "") or None
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    budget_s = int(inputs.get("budget_s") or 0)
    if atom == "prepare_over_budget_reap":
        from lokay.proc.prepare_over_budget_reap import prepare
        from lokay.proc.over_budget_catalog import SLOTS

        return prepare(pass_dir=pass_dir, budget_s=budget_s, slot_count=SLOTS)
    if atom == "over_budget_catalog":
        from lokay.proc.over_budget_catalog import run

        return run(
            up.get("prepare_over_budget_reap") or {},
            config_path=config,
            live=live,
            budget_s=budget_s,
        )
    if atom == "summarize_over_budget_reap":
        from lokay.proc.summarize_over_budget_reap import summarize

        return summarize(up.get("over_budget_catalog") or {})
    return None
