"""Purely classify one repository PR listing as actionable or manual."""

from lokay.passkit.support import is_manual_pr


def classify(selected: dict, listed: dict) -> dict:
    if selected.get("route") != "survey":
        return {**selected, "prs": [], "actionable": 0, "manual": 0}
    if listed.get("route") != "listed":
        return {
            **selected,
            "route": "failed",
            "prs": [],
            "actionable": 0,
            "manual": 0,
            "listed": listed.get("listed"),
        }
    prs = list(listed.get("prs") or [])
    manual = sum(is_manual_pr(pr) for pr in prs)
    return {
        **selected,
        "route": "record",
        "prs": prs,
        "actionable": len(prs) - manual,
        "manual": manual,
        "listed": listed.get("listed"),
    }
