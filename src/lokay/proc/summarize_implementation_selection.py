"""Return the authored implementation-selection terminal result."""


def summarize(persisted: dict) -> dict:
    route = str(persisted.get("route") or ("selected" if persisted.get("selected") else "none"))
    return {"ok": True, "route": route, "result": persisted}
