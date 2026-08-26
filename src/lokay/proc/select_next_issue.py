"""Pick the first listed issue. Two small functions: classify, then select."""

from lokay.proc.classify_open_issues import classify


def select(listed: dict) -> dict:
    classified = classify(listed)
    if classified.get("route") != "listed":
        return {
            "ok": True,
            "route": "none",
            "reason": classified.get("reason") or "skip",
        }
    rows = list(classified.get("issues") or [])
    if not rows:
        return {"ok": True, "route": "none", "reason": "no_open_issue"}
    row = dict(rows[0])
    return {
        "ok": True,
        "route": "issue",
        "leftover": max(0, len(rows) - 1),
        **row,
    }
