"""Stabilize one optional leftover-closeout park effect."""


def record(selected: dict, parked: dict) -> dict:
    return dict(parked if parked.get("ok") else selected)
