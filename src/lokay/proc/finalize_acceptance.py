"""Reduce first verify + optional acceptance repair/recheck to a publish route."""

from __future__ import annotations


def finalize(first: dict, recheck: dict, repair: dict | None = None) -> dict:
    """publish if first or recheck accepted; else repair_terminal (ok:true)."""
    first = dict(first or {})
    recheck = dict(recheck or {})
    repair = dict(repair or {})
    if not first and not recheck:
        return {
            "ok": True,
            "route": "not_applicable",
            "accepted": False,
            "reason": "acceptance_absent",
            "failed_evidence": [],
        }
    if first.get("accepted") is True or first.get("route") == "publish":
        return {
            "ok": True,
            "route": "publish",
            "accepted": True,
            "reason": "acceptance_first",
            "failed_evidence": [],
        }
    if recheck.get("accepted") is True or recheck.get("route") == "publish":
        return {
            "ok": True,
            "route": "publish",
            "accepted": True,
            "reason": "acceptance_recheck",
            "failed_evidence": [],
        }
    failed = list(
        recheck.get("failed_evidence")
        or first.get("failed_evidence")
        or []
    )
    # Repair attempted but still red — terminal for this delivery tick.
    reason = "acceptance_repair_terminal"
    if repair and not (
        repair.get("skipped") or repair.get("reason") == "condition_not_met"
    ):
        reason = "acceptance_repair_exhausted"
    return {
        "ok": True,
        "route": "repair_terminal",
        "accepted": False,
        "reason": reason,
        "failed_evidence": failed,
    }
