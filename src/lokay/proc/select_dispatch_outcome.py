"""Reduce mutually exclusive launch effects to one direct Fala route."""


def select(success: dict, failure: dict) -> dict:
    if success.get("route") == "receipt":
        return {"ok": True, "route": "receipt", "stuck_changed": True, **success}
    if failure.get("route") == "blocked":
        return {"ok": True, "route": "blocked", "stuck_changed": True, **failure}
    return (
        {"ok": True, "route": "retry_later", "stuck_changed": True, **failure}
        if failure
        else {"ok": True, "route": "done", "stuck_changed": False}
    )
