"""Purely expose one closed mechanical intake-check route."""


def classify(request: dict) -> dict:
    return {
        "ok": True,
        "route": request.get("check") if request.get("route") == "read" else "terminal",
        "reason": request.get("reason") or "",
    }
