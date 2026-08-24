"""Purely identify source paths outside an explicit issue scope."""

from lokay.proc.assert_real_diff import _paths_outside_scope


def classify(changed: dict, issue: dict, presence: dict) -> dict:
    if issue.get("route") != "required" or presence.get("route") != "continue":
        return {"ok": True, "route": "continue", "reason": "", "extra_paths": []}
    extra = _paths_outside_scope(
        list(changed.get("paths") or []), list(issue.get("paths") or [])
    )
    return {
        "ok": True,
        "route": "terminal" if extra else "continue",
        "reason": "ticket_scope_extra" if extra else "",
        "extra_paths": extra,
        "required_paths": issue.get("paths") or [],
    }
