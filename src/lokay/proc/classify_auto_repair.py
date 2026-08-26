"""Classify whether auto-repair should run, or the factory should host.

Leftover / leftover-probe / pass_ceiling / daemon_exec preflight are not
repair. Those host factory_pass. Only a confirmed carrier stall repairs once.
"""

from __future__ import annotations

_MOVING = frozenset(
    {"progress", "running", "waiting", "repairing", "idle"}
)
_CARRIER = frozenset(
    {
        "carrier_failed",
        "host_failed",
        "source_integrity_failed",
        "confirmed_stall",
    }
)
_NOT_REPAIR = frozenset(
    {
        "pass_ceiling",
        "preflight_failed",
        "probe_failed",
        "leftover_probe_failed",
        "candidates_exceed_slots",
        "catalog_exceeds_slots",
        "leftover_park_failed",
        "prepare_failed",
    }
)


def classify(begin: dict, last_pass: dict | None = None) -> dict:
    receipt = last_pass if isinstance(last_pass, dict) else {}
    health = str(receipt.get("health") or begin.get("health") or "")
    remaining = receipt.get("remaining") if isinstance(receipt.get("remaining"), dict) else {}
    started = int(remaining.get("issue_to_pr_started") or 0)
    if started > 0 or health in _MOVING:
        return {"ok": True, "route": "pass", "reason": "moving_forward", "health": health}
    if health in _NOT_REPAIR or str(receipt.get("reason") or "") in _NOT_REPAIR:
        return {"ok": True, "route": "pass", "reason": "host_not_repair", "health": health}
    if health in _CARRIER:
        return {"ok": True, "route": "repair", "reason": "carrier_stall", "health": health}
    return {"ok": True, "route": "pass", "reason": "host_factory", "health": health}
