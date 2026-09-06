"""Return the explicit no-effect terminal for a closed or non-deliverable issue."""

from __future__ import annotations


def terminal(resolved: dict) -> dict:
    return {
        "ok": True,
        "stopped": True,
        "reason": resolved.get("reason") or "issue_closed",
        "issue": resolved.get("issue"),
    }
