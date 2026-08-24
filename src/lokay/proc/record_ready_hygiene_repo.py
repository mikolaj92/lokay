"""Stabilize one optional ready-hygiene repository probe."""


def record(selected: dict, classified: dict) -> dict:
    return dict(classified if classified.get("ok") else selected)
