"""Structured terminal for local verification only (not publish)."""

from __future__ import annotations


def terminal(finalize_local_tests: dict) -> dict:
    route = str(finalize_local_tests.get("route") or "fail")
    if route == "not_applicable":
        return {"ok": True, "route": "skip", "reason": "local_verification_not_applicable",
                "finalize_route": route, "status": "skipped"}
    ok = route == "publish"
    return {
        "ok": ok,
        "route": "pass" if ok else "fail",
        "reason": "local_verification",
        "finalize_route": route,
        "status": "succeeded" if ok else "failed",
    }
