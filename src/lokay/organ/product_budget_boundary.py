"""Fala bindings for eight authored serial product-pass slots."""

from typing import Any

SLOTS = 8


def _slot(atom):
    return int(atom.rsplit("_", 1)[1])


def handle_product_budget(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "prepare_product_budget":
        from lokay.proc.prepare_product_budget import prepare

        return prepare(
            config_path=config,
            live=live,
            max_passes=int(inputs.get("max_passes") or 8),
            slot_count=SLOTS,
        )
    slot = _slot(atom) if atom.rsplit("_", 1)[-1].isdigit() else 0
    if atom.startswith("select_product_pass_slot_"):
        from lokay.proc.select_product_pass_slot import select

        return select(
            up.get("prepare_product_budget") or {},
            up.get(f"finalize_product_pass_{slot-1}") or {},
            slot=slot,
        )
    if atom.startswith("run_product_factory_pass_"):
        from lokay.proc.run_product_factory_pass import run

        return run(config_path=config, live=live, slot=slot)
    if atom.startswith("run_product_leftover_closeout_"):
        from lokay.proc.run_product_leftover_closeout import run

        return run(config_path=config, live=live)
    if atom.startswith("apply_product_leftover_"):
        from lokay.proc.apply_product_leftover import apply

        return apply(
            up.get(f"run_product_factory_pass_{slot}") or {},
            up.get(f"run_product_leftover_closeout_{slot}") or {},
        )
    if atom.startswith("record_product_pass_"):
        from lokay.proc.record_product_pass import record

        return record(
            up.get(f"select_product_pass_slot_{slot}") or {},
            up.get(f"apply_product_leftover_{slot}") or {},
            up.get(f"finalize_product_pass_{slot-1}") or {},
        )
    if atom.startswith("classify_product_pass_"):
        from lokay.proc.classify_product_pass import classify

        return classify(
            up.get("prepare_product_budget") or {},
            up.get(f"record_product_pass_{slot}") or {},
        )
    if atom.startswith("classify_product_plateau_"):
        from lokay.proc.classify_product_plateau import classify

        return classify(up.get(f"classify_product_pass_{slot}") or {})
    if atom.startswith("decide_product_pass_stop_"):
        from lokay.proc.decide_product_pass_stop import decide

        return decide(
            up.get("prepare_product_budget") or {},
            up.get(f"classify_product_plateau_{slot}") or {},
        )
    if atom.startswith("finalize_product_pass_"):
        from lokay.proc.finalize_product_pass import finalize

        return finalize(
            up.get("prepare_product_budget") or {},
            up.get(f"decide_product_pass_stop_{slot}") or {},
        )
    if atom == "select_product_budget_result":
        from lokay.proc.select_product_budget_result import select

        return select(
            up.get("prepare_product_budget") or {},
            [up.get(f"finalize_product_pass_{i}") or {} for i in range(1, SLOTS + 1)],
        )
    return None
