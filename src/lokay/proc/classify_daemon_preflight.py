"""Purely classify one closed daemon preflight result."""


def classify(preflight: dict) -> dict:
    if preflight.get("ok"):
        route = "product"
    elif preflight.get("operational_overlap"):
        route = "overlap"
    elif not preflight.get("carrier_ok"):
        route = "carrier_failed"
    else:
        route = "repair"
    return {"ok": True, "route": route, "preflight": preflight}
