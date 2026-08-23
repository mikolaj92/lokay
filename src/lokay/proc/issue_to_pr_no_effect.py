"""Return the explicit no-effect terminal for a closed issue."""

from __future__ import annotations


def terminal(resolved: dict) -> dict:
    return {
        "ok": True,
        "stopped": True,
        "reason": "issue_closed",
        "issue": resolved.get("issue"),
    }
