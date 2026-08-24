"""Stabilize existing, absent, or failed covering-PR evidence."""


def record(found: dict) -> dict:
    return {"ok": True, **{k: v for k, v in found.items() if k != "ok"}}
