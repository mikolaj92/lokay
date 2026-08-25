"""Fala bindings for authored daemon entry routing."""

from typing import Any


def handle_daemon_entry(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    classified = up.get("classify_daemon_preflight") or {}
    if atom == "classify_daemon_preflight":
        from lokay.proc.classify_daemon_preflight import classify

        return classify(dict(inputs.get("preflight") or {}))
    if atom == "run_daemon_product_cycle":
        from lokay.proc.run_daemon_product_cycle import run

        return run(
            config_path=str(inputs.get("config_path") or ""),
            max_passes=max(1, int(inputs.get("max_passes") or 8)),
        )
    if atom == "run_initial_self_repair":
        from lokay.proc.run_initial_self_repair import run

        return run(
            classified.get("preflight") or {},
            config_path=str(inputs.get("config_path") or ""),
        )
    if atom == "daemon_entry_terminal":
        from lokay.proc.daemon_entry_terminal import terminal

        return terminal(
            classified,
            up.get("run_daemon_product_cycle") or {},
            up.get("run_initial_self_repair") or {},
        )
    return None
