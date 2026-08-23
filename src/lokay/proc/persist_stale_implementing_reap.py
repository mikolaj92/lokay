"""Finalize the already-applied stale-stage recovery reaction."""


def persist(updated: dict) -> dict:
    return {**updated, "ok": True}
