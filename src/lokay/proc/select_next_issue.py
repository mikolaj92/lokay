"""Pick the first open issue. One implement per pass."""


def select(listed: dict) -> dict:
    rows = list(listed.get("issues") or [])
    if not rows:
        return {"ok": True, "route": "none", "reason": "no_open_issue"}
    row = dict(rows[0])
    return {"ok": True, "route": "issue", **row}
