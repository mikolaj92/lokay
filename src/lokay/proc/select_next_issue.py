"""Pick one listed issue. Classify list facts, then pick. One implement per pass."""

from lokay.proc.classify_open_issues import classify


def pick(classified: dict) -> dict:
    if classified.get("route") != "listed":
        return {
            "ok": True,
            "route": "none",
            "reason": classified.get("reason") or "skip",
        }
    rows = list(classified.get("issues") or [])
    if not rows:
        return {"ok": True, "route": "none", "reason": "no_open_issue"}
    leftover = max(0, len(rows) - 1)
    return {
        **dict(rows[0]),
        "ok": True,
        "route": "issue",
        "leftover": leftover,
    }


def select(listed: dict) -> dict:
    return pick(classify(listed))
