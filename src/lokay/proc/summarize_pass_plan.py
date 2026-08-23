"""Return the authored pass-plan terminal result."""


def summarize(persisted: dict) -> dict:
    return {"ok": True, "result": persisted}
