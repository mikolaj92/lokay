"""Return one terminal coding outcome without guessing a replacement verdict."""

from __future__ import annotations


def terminal(decision: dict, *, kind: str) -> dict:
    return {"ok": True, "terminal": kind, "decision": decision}
