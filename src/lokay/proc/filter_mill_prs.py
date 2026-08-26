"""Keep mill-prefix PRs. Pure. No GitHub."""


def filter_rows(listed: dict, scope: dict) -> dict:
    if listed.get("ok") is False:
        return {
            "ok": False,
            "error": listed.get("error"),
            "prs": [],
            "count": 0,
        }
    prefix = str(scope.get("prefix") or "ai/fix/").rstrip("/") + "/"
    kept = [
        dict(row)
        for row in listed.get("prs") or []
        if isinstance(row, dict) and str(row.get("branch") or "").startswith(prefix)
    ]
    return {"ok": True, "prs": kept, "count": len(kept)}
