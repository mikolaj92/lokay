"""Stabilize one optional untracked-path check."""


def record(selected: dict, checked: dict) -> dict:
    return dict(checked if checked.get("ok") else selected)
