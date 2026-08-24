"""Purely identify changed source paths outside optional localization scope."""

from lokay.proc.assert_real_diff import _off_goal_paths


def classify(changed: dict, localize: dict, ticket: dict) -> dict:
    if ticket.get("route") != "continue":
        return {
            "ok": True,
            "route": "terminal",
            "reason": ticket.get("reason") or "ticket_scope_extra",
            "off_goal_paths": [],
        }
    scope = list(localize.get("paths") or [])
    off = _off_goal_paths(list(changed.get("paths") or []), scope) if scope else []
    return {
        "ok": True,
        "route": "terminal" if off else "continue",
        "reason": "off_goal" if off else "",
        "off_goal_paths": off,
        "localized_paths": scope,
    }
