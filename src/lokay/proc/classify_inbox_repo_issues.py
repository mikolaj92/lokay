"""Purely exclude stuck-ledger issues from one repository inbox listing."""

from lokay.stuck import is_blocked_in_ledger


def classify(prepared: dict, selected: dict, listed: dict) -> dict:
    if selected.get("route") != "survey":
        return {**selected, "issues": [], "blocked": []}
    if listed.get("route") != "listed":
        return {
            **selected,
            "route": "failed",
            "issues": [],
            "blocked": [],
            "listed": listed.get("listed"),
        }
    ready = []
    blocked = []
    for issue in listed.get("issues") or []:
        number = int(issue.get("number", -1))
        if is_blocked_in_ledger(prepared.get("stuck") or {}, selected["repo"], number):
            blocked.append(number)
        else:
            ready.append(issue)
    return {
        **selected,
        "route": "record",
        "issues": ready,
        "blocked": blocked,
        "listed": listed.get("listed"),
    }
