"""Purely classify orphan ready labels from one repository listing."""

WORK_READY_LABEL = "work:ready"


def classify(selected: dict, listed: dict) -> dict:
    if selected.get("route") != "probe":
        return {**selected, "candidates": []}
    if listed.get("route") != "listed":
        return {
            **selected,
            "route": "failed",
            "candidates": [],
            "error": listed.get("error"),
        }
    candidates = [
        x
        for x in listed.get("issues") or []
        if WORK_READY_LABEL not in set(x.get("labels") or [])
    ]
    return {**selected, "route": "record", "candidates": candidates}
