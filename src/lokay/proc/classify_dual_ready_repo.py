"""Purely classify one open dual-label ready listing."""

from lokay.proc.catalog_work import issue_labels


def classify(selected: dict, listed: dict) -> dict:
    if selected.get("route") != "probe":
        return {**selected, "issues": []}
    if listed.get("route") == "failed":
        return {
            **selected,
            "ok": True,
            "route": "failed",
            "error": str(listed.get("error") or ""),
            "issues": [],
        }
    needed = [
        str(name)
        for name in selected.get("labels") or ["work:ready", "ai:ready"]
        if str(name)
    ]
    hits = [
        issue
        for issue in listed.get("issues") or []
        if set(needed) <= set(issue_labels(issue))
    ]
    return {
        **selected,
        "ok": True,
        "route": "wake" if hits else "empty",
        "issues": hits,
    }
