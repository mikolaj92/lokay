"""Return the authored occupancy-refresh terminal result."""


def summarize(persisted: dict) -> dict:
    return {"ok": True, "result": persisted}
