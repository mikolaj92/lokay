"""Fala bindings for one inbox-survey catalog atom (no 30-slot unroll)."""

from typing import Any

SLOTS = 30


def handle_inbox_survey(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "")
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "prepare_inbox_survey":
        from lokay.proc.prepare_inbox_survey import prepare

        return prepare(pass_dir=pass_dir, slot_count=SLOTS)
    if atom == "inbox_survey_catalog":
        from lokay.proc.inbox_survey_catalog import run

        return run(
            up.get("prepare_inbox_survey") or {},
            pass_dir=pass_dir,
            config_path=config,
            live=live,
        )
    if atom == "update_inbox_survey_stamp":
        from lokay.proc.update_inbox_survey_stamp import update

        return update(
            pass_dir=pass_dir, persisted=up.get("inbox_survey_catalog") or {}
        )
    return None
