"""Publish gate: local verification + acceptance + stamps — separate from verify."""

from __future__ import annotations


def select(
    *,
    finalize_local_tests: dict,
    assert_stamps_committed: dict,
    finalize_acceptance: dict | None = None,
    verify_acceptance: dict | None = None,
) -> dict:
    """Route publish only when each upstream atom is independently green.

    Prefer finalize_acceptance (first verify or post-repair recheck). Always
    ok:true with route publish|block so the effector stays succeeded.
    """
    acceptance = dict(finalize_acceptance or {}) or dict(verify_acceptance or {})
    if finalize_local_tests.get("route") != "publish":
        return {
            "ok": True,
            "route": "block",
            "reason": "local_verification_not_publish",
            "failed_atom": "finalize_local_tests",
        }
    if acceptance.get("accepted") is not True or acceptance.get("route") != "publish":
        return {
            "ok": True,
            "route": "block",
            "reason": "acceptance_not_publish",
            "failed_atom": "finalize_acceptance"
            if finalize_acceptance
            else "verify_acceptance",
        }
    if (
        assert_stamps_committed.get("ok") is not True
        or assert_stamps_committed.get("route") != "publish"
    ):
        return {
            "ok": True,
            "route": "block",
            "reason": "stamps_not_committed",
            "failed_atom": "assert_stamps_committed",
            "dirty_stamps": list(assert_stamps_committed.get("dirty_stamps") or []),
        }
    return {"ok": True, "route": "publish", "reason": "publish_gate_open"}
