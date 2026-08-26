"""Fala bindings for one leftover-closeout catalog atom (no 30-slot unroll)."""

from typing import Any


def handle_leftover_closeout(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "prepare_leftover_closeout":
        from lokay.proc.leftover_catalog import REPO_SLOTS
        from lokay.proc.prepare_leftover_closeout import prepare

        return prepare(config_path=config, live=live, slot_count=REPO_SLOTS)
    if atom == "leftover_catalog":
        from lokay.proc.leftover_catalog import run

        return run(
            up.get("prepare_leftover_closeout") or {},
            config_path=config,
            live=live,
        )
    if atom == "update_leftover_stamp":
        from lokay.proc.update_leftover_stamp import update

        return update(up.get("leftover_catalog") or {}, config_path=config)
    return None
