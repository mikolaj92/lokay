"""Classify a listed page: listed, or skip when empty / overflow."""


def classify(listed: dict) -> dict:
    rows = list(listed.get("issues") or [])
    if not rows:
        reason = "overflow" if listed.get("overflow") else "empty"
        return {
            "ok": True,
            "route": "skip",
            "reason": reason,
            "skipped": True,
            "issues": [],
            "count": 0,
        }
    return {
        "ok": True,
        "route": "listed",
        "issues": rows,
        "count": len(rows),
        "overflow": bool(listed.get("overflow")),
    }
