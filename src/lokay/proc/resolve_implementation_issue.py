"""Reduce the current issue state to open or no-effect."""

from __future__ import annotations


def resolve(issue: dict) -> dict:
    opened = str(issue.get("state") or "").upper() == "OPEN"
    return {
        "ok": True,
        "route": "open" if opened else "closed",
        "issue": int(issue.get("number") or 0),
    }
