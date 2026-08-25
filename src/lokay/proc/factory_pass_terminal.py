"""Lift the idle or hosted factory_pass result for the path normalizer."""

from __future__ import annotations

from typing import Any


def terminal(classified: dict[str, Any], hosted: dict[str, Any], idle: dict[str, Any]) -> dict[str, Any]:
    if classified.get("route") == "idle":
        payload = idle.get("result") if isinstance(idle.get("result"), dict) else idle
        if not isinstance(payload, dict) or not payload:
            payload = {
                "ok": True,
                "health": "idle",
                "idle": True,
                "lane": "idle",
                "reason": classified.get("reason") or "recent_empty_survey",
            }
        out = dict(payload)
        out.setdefault("lane", "idle")
        out.setdefault("health", "idle")
        out.setdefault("idle", True)
        return {"ok": True, "result": out}
    payload = hosted.get("result") if isinstance(hosted.get("result"), dict) else hosted
    if not isinstance(payload, dict) or not payload:
        payload = {"ok": False, "health": "hosted_result_missing"}
    return {"ok": True, "result": payload}
