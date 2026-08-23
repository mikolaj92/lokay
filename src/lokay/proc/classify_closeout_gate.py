"""Purely route one PR after issue and PR metadata facts."""


def classify(inspected: dict, issue: dict) -> dict:
    if issue.get("route") == "closed":
        route = "issue_closed"
    elif inspected.get("route") in {"manual", "conflict"}:
        route = str(inspected["route"])
    else:
        route = "checks"
    return {
        "ok": True,
        "route": route,
        "reason": {
            "issue_closed": "issue_closed",
            "manual": "manual",
            "conflict": "conflict",
        }.get(route, ""),
        "inspected": inspected,
        "issue_read": issue,
    }
