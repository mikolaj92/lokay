"""Closeout counter/park effects. One matrix: merge_policy (no second gate)."""

from __future__ import annotations

from typing import Any, Mapping

from lokay.envelope import ok
from lokay.merge_policy import WAITING_REASONS, WAITING_REMAINING_FIELDS

COUNTERS = (
    "pending_checks",
    "no_checks_blocked",
    "merge_conflicts",
    "needs_repair",
    "mergeable_green",
    "merge_disabled",
    "review_limbo",
)


def apply_deltas(counters: dict[str, int], deltas: Mapping[str, int]) -> None:
    for key, n in deltas.items():
        counters[key] = max(0, int(counters.get(key) or 0) + int(n))


def wait_deltas(reason: str, *, green: bool = False) -> dict[str, int]:
    out: dict[str, int] = {}
    field = WAITING_REMAINING_FIELDS.get(reason)
    if field:
        out[field] = 1
    if green and reason == "merge_disabled":
        out["mergeable_green"] = 1
    return out


def route_deltas(route: str, reason: str) -> dict[str, int]:
    if route == "repair":
        return {"needs_repair": 1}
    if route == "wait":
        return wait_deltas(reason, green=True)
    if route == "merge":
        return {"mergeable_green": 1}
    return {}


def triage_skip_deltas(tri: Mapping[str, Any]) -> dict[str, int]:
    reason = str(tri.get("reason") or "")
    if tri.get("waiting") or reason in WAITING_REASONS:
        out = wait_deltas(reason)
        out["mergeable_green"] = -1
    elif tri.get("repairable") or reason == "checks_failed":
        out = {"needs_repair": 1}
        if reason == "checks_failed":
            out["mergeable_green"] = -1
    else:
        out = {"mergeable_green": -1, "review_limbo": 1}
    if tri.get("reason") == "merge_conflicts":
        out["merge_conflicts"] = int(out.get("merge_conflicts") or 0) + 1
    return out


def should_review_repair(tri: Mapping[str, Any]) -> bool:
    reason = str(tri.get("reason") or "")
    if tri.get("waiting") or reason in WAITING_REASONS:
        return False
    return bool(tri.get("repairable") or reason == "checks_failed")


def park_needs_review(tri: Mapping[str, Any]) -> bool:
    review = tri.get("review")
    return bool(
        tri.get("escalated")
        or tri.get("needs_review")
        or (isinstance(review, dict) and (review.get("verdict") == "needs_human" or review.get("secrets") is True))
    )


def pr_envelope(
    *,
    repo: str,
    pr: int,
    route: str,
    reason: str,
    still_open: bool,
    actions: list[dict[str, Any]],
    repair_budget: int,
    progress: int,
    remaining_closed: int,
    counters: Mapping[str, int],
) -> dict[str, Any]:
    return ok(
        repo=repo, pr=pr, route=route, reason=reason, still_open=still_open,
        merged=not still_open, actions=actions, repair_budget=repair_budget,
        progress=progress, remaining_closed=remaining_closed, **dict(counters),
    )
