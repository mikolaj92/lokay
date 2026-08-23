"""Stabilize the optional hard-fact branch into one closed route."""


def select(target: dict, covering: dict) -> dict:
    if target.get("route") != "candidate":
        return {"ok": True, "route": "none", "reason": target.get("reason")}
    return dict(covering)
