"""Pick the first open mill PR. One review/repair/merge per pass."""


def select(listed: dict) -> dict:
    if listed.get("ok") is False:
        return {
            "ok": False,
            "route": "none",
            "reason": "list_failed",
            "error": listed.get("error"),
        }
    for row in listed.get("prs") or []:
        if not isinstance(row, dict):
            continue
        if row.get("repo") and row.get("pr") and row.get("branch"):
            return {"ok": True, "route": "pr", **dict(row)}
    return {"ok": True, "route": "none", "reason": "no_open_pr"}
