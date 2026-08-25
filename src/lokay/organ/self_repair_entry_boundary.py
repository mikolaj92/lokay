"""Fala bindings for authored self-repair entry."""

from typing import Any


def handle_self_repair_entry(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    prepared = up.get("prepare_self_repair_entry") or {}
    entry = up.get("classify_self_repair_entry") or {}
    run = up.get("record_authored_self_repair") or {}
    outcome = up.get("classify_self_repair_entry_outcome") or {}
    selected = up.get("select_self_repair_entry_result") or {}
    if atom == "prepare_self_repair_entry":
        from lokay.proc.prepare_self_repair_entry import prepare

        return prepare(
            config_path=str(inputs.get("config_path") or "") or None,
            preflight=dict(inputs.get("preflight") or {}),
        )
    if atom == "classify_self_repair_entry":
        from lokay.proc.classify_self_repair_entry import classify

        return classify(prepared)
    if atom in {
        "record_self_repair_entry_start",
        "record_self_repair_entry_failure",
        "record_self_repair_entry_success",
    }:
        from lokay.proc.record_self_repair_entry_event import record

        phase = (
            "start"
            if atom.endswith("start")
            else (
                "failed" if atom.endswith("failure") else "validated_restart_required"
            )
        )
        return record(
            prepared,
            phase=phase,
            reason=(
                str(selected.get("reason") or entry.get("reason") or "")
                if phase == "failed"
                else ""
            ),
            commit=(
                str(selected.get("commit") or "")
                if phase.startswith("validated")
                else ""
            ),
        )
    if atom == "run_authored_self_repair":
        from lokay.proc.run_authored_self_repair import run as execute

        return execute(prepared)
    if atom == "record_authored_self_repair":
        from lokay.proc.record_authored_self_repair import record

        return record(entry, up.get("run_authored_self_repair") or {})
    if atom == "classify_self_repair_entry_outcome":
        from lokay.proc.classify_self_repair_entry_outcome import classify

        return classify(run)
    if atom == "write_self_repair_restart_marker":
        from lokay.proc.write_self_repair_restart_marker import write

        return write(prepared, outcome)
    if atom == "select_self_repair_entry_result":
        from lokay.proc.select_self_repair_entry_result import select

        return select(
            prepared, entry, outcome, up.get("write_self_repair_restart_marker") or {}
        )
    if atom == "self_repair_entry_terminal":
        from lokay.proc.self_repair_entry_terminal import terminal

        return terminal(selected)
    return None
