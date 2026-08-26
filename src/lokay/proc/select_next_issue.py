"""Pick the first open issue. One implement per pass. Leftover is next pass."""


def select(listed: dict) -> dict:
    if listed.get("skipped") or listed.get("route") == "skip":
        return {
            "ok": True,
            "route": "none",
            "reason": listed.get("reason") or "skip",
        }
    rows = list(listed.get("issues") or [])
    if not rows:
        return {"ok": True, "route": "none", "reason": "no_open_issue"}
    row = dict(rows[0])
    leftover = max(0, len(rows) - 1)
    return {
        "ok": True,
        "route": "issue",
        "leftover": leftover,
        **row,
    }
