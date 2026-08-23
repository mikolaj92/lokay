"""Purely classify the authored PR-triage terminal result."""

from lokay.closeout import park_needs_review, should_review_repair, triage_skip_deltas


def classify(triaged: dict) -> dict:
    tri = dict(triaged.get("triage") or {})
    if not tri.get("ok"):
        return {"ok": True, "route": "final", "reason": "triage_error", "deltas": {}}
    if not tri.get("skipped"):
        return {
            "ok": True,
            "route": "merged",
            "reason": "",
            "deltas": {"mergeable_green": -1},
            "triage": tri,
        }
    route = "repair" if should_review_repair(tri) else "final"
    return {
        "ok": True,
        "route": route,
        "reason": str(tri.get("reason") or ""),
        "deltas": triage_skip_deltas(tri),
        "review": dict(tri.get("review") or {}),
        "step": "pr_review_repair",
        "park_manual": park_needs_review(tri),
        "triage": tri,
    }
