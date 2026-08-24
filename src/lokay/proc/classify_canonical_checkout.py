"""Purely route a canonical checkout status fact."""


def classify(prepared: dict, status: dict) -> dict:
    if prepared.get("route") != "status":
        return {
            "ok": True,
            "route": "terminal",
            "reason": (
                "planned"
                if prepared.get("route") == "planned"
                else prepared.get("reason", "checkout_unavailable")
            ),
        }
    if status.get("route") != "classify":
        return {
            "ok": True,
            "route": "terminal",
            "reason": status.get("reason") or "status_failed",
        }
    return {
        "ok": True,
        "route": "dirty" if status.get("dirty") else "clean",
        "reason": "",
    }
