"""Fala bindings for one ready-hygiene catalog atom (no 30-slot unroll)."""

from typing import Any

CATALOG_SLOTS = 30


def handle_ready_hygiene(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "prepare_ready_hygiene":
        from lokay.proc.prepare_ready_hygiene import prepare

        return prepare(config_path=config, live=live, slot_count=CATALOG_SLOTS)
    if atom == "ready_hygiene_catalog":
        from lokay.proc.ready_hygiene_catalog import run

        return run(
            up.get("prepare_ready_hygiene") or {},
            config_path=config,
            live=live,
        )
    if atom == "update_ready_hygiene_stamp":
        from lokay.proc.update_ready_hygiene_stamp import update

        return update(up.get("ready_hygiene_catalog") or {}, config_path=config)
    return None
