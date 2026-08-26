"""Return the authored implementation-selection terminal result."""


def summarize(persisted: dict) -> dict:
    raw = str(persisted.get("route") or ("selected" if persisted.get("selected") else "none"))
    # Parent factory_pass when is binary: selected work vs housecleaning.
    route = "selected" if raw == "selected" else "none"
    return {"ok": True, "route": route, "result": persisted}
