"""Stabilize optional issue, budget, coder, and diff facts into one route."""


def select(selected: dict, issue: dict, budget: dict, coder: dict, diff: dict) -> dict:
    if selected.get("route") != "receipt":
        return dict(selected)
    if budget.get("route") == "keep":
        return {**budget, "route": "keep"}
    if budget.get("closed"):
        return {**budget, "route": "reap", "reason": "issue_closed"}
    if coder.get("route") == "reap":
        return {**coder, "route": "reap", "reason": "over_budget"}
    return dict(
        diff if diff.get("ok") else {**coder, "route": "keep", "reason": "coder_live"}
    )
