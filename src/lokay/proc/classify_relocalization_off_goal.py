"""Purely classify remaining changed paths outside the localization scope."""

from lokay.proc.assert_real_diff import _off_goal_paths


def classify(evidence: dict, changed: dict, restored: dict) -> dict:
    remaining = [
        x
        for x in changed.get("changed") or []
        if x not in set(restored.get("restored_paths") or [])
    ]
    off = _off_goal_paths(remaining, list(evidence.get("localized") or []))
    return {
        "ok": True,
        "route": "agent" if off else "terminal",
        "off_goal_paths": off,
        "remaining": remaining,
        "restored_paths": restored.get("restored_paths") or [],
        "reason": "on_goal" if not off else "",
    }
