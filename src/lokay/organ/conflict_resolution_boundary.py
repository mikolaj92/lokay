"""Fala bindings for one bounded pull-request conflict resolution."""

from typing import Any


def handle_conflict_resolution(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "")
    config = str(inputs.get("config_path") or "") or None
    live = bool(inputs.get("live"))
    if atom == "select_conflicting_pr":
        from lokay.proc.select_conflicting_pr import select

        return select(pass_dir=pass_dir)
    if atom == "close_conflicting_pr":
        from lokay.proc.close_conflicting_pr import close

        return close(
            up.get("select_conflicting_pr") or {}, config_path=config, live=live
        )
    if atom == "select_conflict_close":
        target, closed = (
            up.get("select_conflicting_pr") or {},
            up.get("close_conflicting_pr") or {},
        )
        return (
            closed
            if target.get("route") == "conflict"
            else {"ok": True, "route": "none"}
        )
    if atom == "resolve_conflict_issue":
        from lokay.proc.resolve_conflict_issue import resolve

        return resolve(pass_dir=pass_dir, closed=up.get("select_conflict_close") or {})
    if atom == "select_conflict_issue":
        closed, resolved = (
            up.get("select_conflict_close") or {},
            up.get("resolve_conflict_issue") or {},
        )
        return (
            resolved
            if closed.get("route") == "closed"
            else {"ok": True, "route": closed.get("route") or "failed"}
        )
    if atom == "clear_conflict_stuck_ledger":
        from lokay.proc.clear_conflict_stuck_ledger import clear

        return clear(pass_dir=pass_dir, resolved=up.get("select_conflict_issue") or {})
    if atom == "ready_issue_after_conflict":
        from lokay.proc.ready_issue_after_conflict import apply

        return apply(
            up.get("clear_conflict_stuck_ledger") or {}, config_path=config, live=live
        )
    if atom == "reduce_conflict_resolution":
        from lokay.passkit.working import load_begin_working
        from lokay.proc.reduce_conflict_resolution import reduce_state

        _, working = load_begin_working(pass_dir)
        target = up.get("select_conflicting_pr") or {}
        if target.get("route") == "none":
            return {"ok": True, "route": "none"}
        return reduce_state(
            working=working,
            target=target,
            closed=up.get("select_conflict_close") or {},
            resolved=up.get("select_conflict_issue") or {},
            cleared=up.get("clear_conflict_stuck_ledger") or {},
            ready=up.get("ready_issue_after_conflict") or {},
        )
    if atom == "record_conflict_resolution":
        from lokay.proc.record_conflict_resolution import record

        return record(
            pass_dir=pass_dir, reduced=up.get("reduce_conflict_resolution") or {}
        )
    if atom == "summarize_conflict_resolution":
        from lokay.proc.summarize_conflict_resolution import summarize

        return summarize(up.get("record_conflict_resolution") or {})
    return None
