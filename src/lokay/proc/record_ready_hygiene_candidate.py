"""Stabilize one optional ready-hygiene mutation effect."""


def record(selected: dict, removed: dict) -> dict:
    return dict(removed if removed.get("ok") else selected)
