"""Choose dispatch vs stop after queue_conflict and optional same-pass next row."""


def classify(queue: dict, nxt: dict | None = None) -> dict:
    route = str(queue.get("route") or "")
    advanced = nxt if isinstance(nxt, dict) else {}
    if route == "ready":
        return {"ok": True, "route": "dispatch", "reason": "queue_ready"}
    if str(advanced.get("route") or "") == "candidate":
        return {"ok": True, "route": "dispatch", "reason": "next_row"}
    return {"ok": True, "route": "none", "reason": route or "no_row"}
