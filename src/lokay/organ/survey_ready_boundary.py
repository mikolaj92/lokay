"""Fala bindings for one ready-survey catalog atom (no 30-slot unroll)."""

from typing import Any

from lokay.execution_contracts import CATALOG_SLOT_COUNT as SLOT_COUNT


def handle_survey_ready(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "")
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "prepare_ready_survey":
        from lokay.proc.prepare_ready_survey import prepare

        return prepare(pass_dir=pass_dir, slot_count=SLOT_COUNT)
    if atom == "ready_survey_catalog":
        from lokay.proc.ready_survey_catalog import run

        return run(
            up.get("prepare_ready_survey") or {},
            pass_dir=pass_dir,
            config_path=config,
            live=live,
        )
    if atom == "update_ready_survey_stamp":
        from lokay.proc.update_ready_survey_stamp import update

        return update(
            pass_dir=pass_dir, finalized=up.get("ready_survey_catalog") or {}
        )
    return None
