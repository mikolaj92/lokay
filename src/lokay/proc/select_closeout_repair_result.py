"""Stabilize the optional closeout repair effect."""


def select(authorized: dict, repaired: dict) -> dict:
    return (
        repaired
        if authorized.get("route") == "repair"
        else {
            "ok": True,
            "repair_used": 0,
            "step": authorized.get("step") or "pr_repair",
            "repair": {},
        }
    )
