"""Stabilize optional stale-stage mutation into one outcome."""


def record(selected: dict, restored: dict) -> dict:
    if selected.get("route") != "apply":
        return dict(selected)
    return dict(restored if restored.get("ok") else {**selected, "route": "failed"})
