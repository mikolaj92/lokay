"""Compatibility facade for the authored self-repair entry Fala."""

from typing import Any


def run_self_repair(
    config_path: str | None, preflight: dict[str, Any]
) -> dict[str, Any]:
    from lokay.proc.self_repair_entry_subflow import run

    return run(config_path=config_path, preflight=preflight)
