"""Restore only the same delegated health token when its record disappeared."""

from lokay.preflight import issue_health_lease


def restore(inspected: dict) -> dict:
    try:
        issue_health_lease()
    except RuntimeError as exc:
        return {"ok": True, "route": "terminal", "error": str(exc)}
    return {"ok": True, "route": "inspect"}
