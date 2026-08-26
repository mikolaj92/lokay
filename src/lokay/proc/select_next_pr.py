"""Pick the first open PR. One review/merge per pass."""


def select(listed: dict) -> dict:
    rows = list(listed.get("prs") or [])
    if not rows:
        return {"ok": True, "route": "none", "reason": "no_open_pr"}
    row = dict(rows[0])
    return {"ok": True, "route": "pr", **row}
