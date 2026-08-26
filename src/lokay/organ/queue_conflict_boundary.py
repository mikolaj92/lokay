"""Fala bindings for one semantic queue-conflict decision."""

from typing import Any


def handle_queue_conflict(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "")
    cfg = ctx["cfg"]
    live = bool(inputs.get("live"))
    if atom == "select_queue_conflict_candidate":
        from lokay.proc.select_queue_conflict_candidate import select

        return select(pass_dir=pass_dir)
    if atom == "check_queue_covering_pr":
        from lokay.proc.check_queue_covering_pr import check

        return check(
            pass_dir=pass_dir, target=up.get("select_queue_conflict_candidate") or {}
        )
    if atom == "select_queue_conflict_gate":
        from lokay.proc.select_queue_conflict_gate import select

        return select(
            up.get("select_queue_conflict_candidate") or {},
            up.get("check_queue_covering_pr") or {},
        )
    if atom in {"queue_conflict_agent", "queue_conflict_retry_agent"}:
        from lokay.proc._common import load_cfg
        from lokay.proc.run_queue_conflict_agent import run
        import argparse

        config = load_cfg(
            argparse.Namespace(config=str(inputs.get("config_path") or "") or None)
        )
        return run(
            cfg=config,
            target=up.get("select_queue_conflict_gate") or {},
            live=live,
            retry_feedback=(
                (up.get("validate_queue_conflict") or {})
                if atom.endswith("retry_agent")
                else None
            ),
        )
    if atom in {"validate_queue_conflict", "validate_queue_conflict_retry"}:
        from lokay.proc.queue_conflict_boundary import validate

        if (up.get("select_queue_conflict_gate") or {}).get("route") in {
            "covered",
            "none",
        }:
            return {"ok": True, "route": "not_applicable"}
        source = (
            "queue_conflict_agent"
            if atom == "validate_queue_conflict"
            else "queue_conflict_retry_agent"
        )
        return validate(str((up.get(source) or {}).get("stdout") or ""))
    if atom == "select_queue_conflict_outcome":
        from lokay.proc.queue_conflict_boundary import select

        return select(
            up.get("select_queue_conflict_candidate") or {},
            up.get("select_queue_conflict_gate") or {},
            up.get("validate_queue_conflict") or {},
            up.get("validate_queue_conflict_retry") or {},
        )
    if atom == "remove_queue_ready_label":
        from lokay.proc.apply_queue_ready_label_removal import apply

        return apply(
            cfg_flags=cfg,
            live_flags=ctx["live"],
            outcome=up.get("select_queue_conflict_outcome") or {},
        )
    if atom == "select_queue_tracker":
        from lokay.proc.select_queue_tracker import select

        return select(up.get("select_queue_conflict_outcome") or {})
    if atom == "add_queue_tracker_label":
        from lokay.proc.apply_queue_tracker_label import apply

        return apply(
            cfg_flags=cfg,
            live_flags=ctx["live"],
            outcome=up.get("select_queue_conflict_outcome") or {},
        )
    if atom == "record_queue_conflict":
        from lokay.proc.record_queue_conflict import record

        return record(
            pass_dir=pass_dir,
            outcome=up.get("select_queue_conflict_outcome") or {},
            remove=up.get("remove_queue_ready_label") or {},
            tracker=up.get("add_queue_tracker_label") or {},
        )
    if atom == "advance_implementation_selection":
        from lokay.proc.advance_implementation_selection import run

        return run(
            pass_dir=pass_dir, recorded=up.get("record_queue_conflict") or {}
        )
    if atom == "summarize_queue_conflict":
        from lokay.proc.summarize_queue_conflict import summarize

        return summarize(
            up.get("select_queue_conflict_candidate") or {},
            up.get("record_queue_conflict") or {},
            up.get("advance_implementation_selection") or {},
        )
    return None
