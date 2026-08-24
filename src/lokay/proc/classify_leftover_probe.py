"""Purely classify one CLOSED ready-label listing."""


def classify(selected: dict, listed: dict) -> dict:
    if selected.get("route") != "probe":
        return {**selected, "candidates": []}
    if listed.get("route") == "failed":
        return {
            **selected,
            "ok": True,
            "route": "failed",
            "error": str(listed.get("error") or ""),
            "candidates": [],
        }
    return {
        **selected,
        "ok": True,
        "route": "record",
        "candidates": [
            {"repo": selected["repo"], "number": int(n)}
            for n in listed.get("numbers") or []
        ],
    }
