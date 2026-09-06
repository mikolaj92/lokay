"""Publish gate: local verification + acceptance + stamps — separate from verify."""

from __future__ import annotations


def select(
    *,
    finalize_local_tests: dict,
    verify_acceptance: dict,
    assert_stamps_committed: dict,
) -> dict:
    """Route publish only when each upstream atom is independently green."""
    if finalize_local_tests.get("route") != "publish":
        return {
            "ok": False,
            "route": "block",
            "reason": "local_verification_not_publish",
            "failed_atom": "finalize_local_tests",
        }
    if verify_acceptance.get("accepted") is not True or verify_acceptance.get("route") != "publish":
        return {
            "ok": False,
            "route": "block",
            "reason": "acceptance_not_publish",
            "failed_atom": "verify_acceptance",
        }
    if assert_stamps_committed.get("ok") is not True or assert_stamps_committed.get("route") != "publish":
        return {
            "ok": False,
            "route": "block",
            "reason": "stamps_not_committed",
            "failed_atom": "assert_stamps_committed",
            "dirty_stamps": list(assert_stamps_committed.get("dirty_stamps") or []),
        }
    return {"ok": True, "route": "publish", "reason": "publish_gate_open"}
