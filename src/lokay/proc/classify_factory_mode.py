"""Purely route configured live mode and the explicit offline escape."""

import os


def classify(config: dict) -> dict:
    if config.get("live") and config.get("mode") != "live":
        return {"ok": True, "route": "terminal", "reason": "mode_not_live"}
    if os.environ.get("LOKAY_OFFLINE", "").strip() in {"1", "true", "yes"}:
        return {"ok": True, "route": "terminal", "reason": "offline"}
    return {"ok": True, "route": "scope"}
