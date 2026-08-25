"""Fala bindings for authored direct-product entry."""

from typing import Any


def handle_product_entry(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    classified = up.get("classify_product_entry_preflight") or {}
    if atom == "classify_product_entry_preflight":
        from lokay.proc.classify_product_entry_preflight import classify

        return classify(dict(inputs.get("entry_preflight") or {}))
    if atom == "run_product_entry_budget":
        from lokay.proc.run_product_entry_budget import execute

        return execute(
            config_path=str(inputs.get("entry_config_path") or "") or None,
            live=bool(inputs.get("entry_live")),
            max_passes=max(1, int(inputs.get("entry_max_passes") or 8)),
        )
    if atom == "product_entry_terminal":
        from lokay.proc.product_entry_terminal import terminal

        return terminal(classified, up.get("run_product_entry_budget") or {})
    return None
