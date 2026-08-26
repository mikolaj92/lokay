"""Fala bindings for one occupancy-refresh catalog atom (no 30-slot unroll)."""

from typing import Any


def handle_occupancy_refresh(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "")
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "prepare_occupancy_refresh":
        from lokay.proc.occupancy_catalog import SLOTS
        from lokay.proc.prepare_occupancy_refresh import prepare

        return prepare(pass_dir=pass_dir, slot_count=SLOTS)
    if atom == "occupancy_catalog":
        from lokay.proc.occupancy_catalog import run

        return run(
            up.get("prepare_occupancy_refresh") or {},
            pass_dir=pass_dir,
            config_path=config,
            live=live,
        )
    if atom == "persist_occupancy_refresh":
        from lokay.proc.persist_occupancy_refresh import persist

        return persist(
            pass_dir=pass_dir, reduced=up.get("occupancy_catalog") or {}
        )
    if atom == "summarize_occupancy_refresh":
        from lokay.proc.summarize_occupancy_refresh import summarize

        return summarize(up.get("persist_occupancy_refresh") or {})
    return None
