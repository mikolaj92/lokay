"""Purely reduce diff kind and scope facts to a closed progress route."""


def classify(kind: dict, scope: dict) -> dict:
    if scope.get("route") != "continue":
        return {
            "ok": True,
            "route": "terminal",
            "reason": scope.get("reason") or "off_goal",
        }
    value = kind.get("kind")
    return {
        "ok": True,
        "route": "real" if value == "real" else "terminal",
        "reason": (
            ""
            if value == "real"
            else ("plan_only" if value == "plan_only" else "zero_diff")
        ),
    }
