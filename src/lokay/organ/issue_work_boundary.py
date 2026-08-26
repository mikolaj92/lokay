"""Fala bindings for parent step (4) next-row edge and terminal."""

from typing import Any


def handle_issue_work(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    pass_dir = str(inputs.get("pass_dir") or "")
    if atom == "select_next_implement":
        from lokay.proc.advance_implementation_selection import run as advance

        recorded = dict(up.get("queue_conflict") or {})
        if recorded.get("route") == "parked":
            recorded["route"] = "needs_human"
        return advance(pass_dir=pass_dir, recorded=recorded)
    if atom == "classify_issue_dispatch":
        from lokay.proc.classify_issue_dispatch import classify

        return classify(
            up.get("queue_conflict") or {}, up.get("select_next_implement") or {}
        )
    if atom == "summarize_issue_work":
        return {
            "ok": True,
            "route": str((up.get("classify_issue_dispatch") or {}).get("route") or "none"),
            "pass_dir": pass_dir,
            "queue_conflict": up.get("queue_conflict") or {},
            "next_row": up.get("select_next_implement") or {},
            "dispatch_implement": up.get("dispatch_implement") or {},
        }
    return None
