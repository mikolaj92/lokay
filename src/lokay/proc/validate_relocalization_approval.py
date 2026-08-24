"""Physically constrain authoritative agent paths to the current off-goal set."""


def validate(validated: dict, offgoal: dict) -> dict:
    if validated.get("route") != "valid":
        return {
            "ok": True,
            "route": "terminal",
            "reason": "off_goal_not_approved",
            "approved": [],
        }
    allowed = set(offgoal.get("off_goal_paths") or [])
    approved = [x for x in validated.get("paths") or [] if x in allowed]
    return {
        "ok": True,
        "route": "write" if approved else "terminal",
        "reason": "" if approved else "off_goal_not_approved",
        "approved": approved,
    }
