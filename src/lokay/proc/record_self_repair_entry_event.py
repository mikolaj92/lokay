"""Append exactly one self-repair entry event, tolerating unavailable observation storage."""

from pathlib import Path

from lokay.state import append_event


def record(prepared: dict, *, phase: str, reason: str = "", commit: str = "") -> dict:
    event = {"kind": "self_repair", "phase": phase, "issue": prepared.get("issue")}
    if prepared.get("fingerprint"):
        event["fingerprint"] = prepared["fingerprint"]
    if reason:
        event["reason"] = reason
    if commit:
        event["commit"] = commit
    try:
        append_event(Path(prepared["state_path"]), event)
    except Exception as exc:  # noqa: BLE001
        return {"ok": True, "route": "recorded", "event_error": str(exc)}
    return {"ok": True, "route": "recorded"}
