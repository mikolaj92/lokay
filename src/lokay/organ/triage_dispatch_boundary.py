"""Fala bindings for one serial inbox-triage dispatch."""

from typing import Any


def handle_triage_dispatch(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "")
    config = str(inputs.get("config_path") or "") or None
    if atom == "select_triage_target":
        from lokay.proc.select_triage_target import select

        return select(pass_dir=pass_dir)
    if atom == "check_triage_stuck":
        from lokay.proc.check_triage_stuck import check

        return check(pass_dir=pass_dir, target=up.get("select_triage_target") or {})
    if atom == "select_triage_gate":
        from lokay.proc.select_triage_gate import select

        return select(
            up.get("select_triage_target") or {}, up.get("check_triage_stuck") or {}
        )
    if atom == "run_issue_triage_subflow":
        from lokay.proc.run_issue_triage_subflow import run

        return run(up.get("select_triage_gate") or {}, config_path=config)
    if atom == "select_triage_run":
        from lokay.proc.select_triage_run import select

        return select(
            up.get("select_triage_gate") or {}, up.get("run_issue_triage_subflow") or {}
        )
    if atom == "record_triage_dispatch":
        from lokay.proc.record_triage_dispatch import record

        return record(pass_dir=pass_dir, outcome=up.get("select_triage_run") or {})
    if atom == "summarize_triage_dispatch":
        from lokay.proc.summarize_triage_dispatch import summarize

        return summarize(up.get("record_triage_dispatch") or {})
    return None
