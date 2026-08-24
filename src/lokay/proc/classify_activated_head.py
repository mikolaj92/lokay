"""Purely route exact or later canonical HEAD identity."""


def classify(
    prepared: dict, checkout: dict, dirty: dict, fetch: dict, merged: dict, head: dict
) -> dict:
    if checkout.get("route") == "dirty":
        return {
            "ok": True,
            "route": "terminal",
            "reason": "dirty_tree",
            "published": dirty.get("route") == "published",
        }
    for fact in (checkout, fetch, merged, head):
        if fact.get("route") == "terminal":
            return {
                "ok": True,
                "route": "terminal",
                "reason": fact.get("reason") or "activation_failed",
            }
    if prepared.get("route") == "planned":
        return {"ok": True, "route": "terminal", "reason": "planned"}
    return {
        "ok": True,
        "route": "exact" if head.get("head") == prepared.get("commit") else "ancestry",
        "reason": "",
        "head": head.get("head"),
    }
