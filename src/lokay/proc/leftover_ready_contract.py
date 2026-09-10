"""Contract: leftover ai:ready cannot finish a pass at remaining_ready=0.

After #1002 cut the ready survey spine, dual-ready fuel lives on
``leftover_issues``. A pass that still lists those rows but reports
``remaining_ready=0`` / empty ``ready_by_repo`` without an explicit skip
reason is a conduction bug (#1086) — begin must materialize dual-ready into
``ready_by_repo`` (or stamp why the ticket was not takeable).
"""

from __future__ import annotations

from typing import Any

from lokay.proc.walk_issue_leftover import row_is_ready

# Explicit skip reasons that may leave dual-ready unfilled this pass.
EXPLICIT_SKIP_REASONS = frozenset(
    {
        "occupied",
        "foreign_assignee",
        "exhausted",
        "executor_disabled",
        "leftover_overflow",
        "leftover_skip",
        "recent_empty_survey",
        "recent_empty_survey_probe",
        "no_budget",
        "outside_scope",
        "pr_survey_failed",
        "actionable_pr",
        "stuck_or_no_ready",
        "skip_stuck",
        "blocked",
    }
)


def leftover_ready_rows(source: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(source, dict):
        return []
    return [
        dict(row)
        for row in list(source.get("leftover_issues") or [])
        if isinstance(row, dict) and row_is_ready(row)
    ]


def stamped_remaining_ready(working: dict[str, Any] | None) -> int:
    """Ready count as stamped on working — not re-derived from leftover."""
    state = dict(working or {})
    ready_by = dict(state.get("ready_by_repo") or {})
    listed = sum(len(rows or []) for rows in ready_by.values())
    if listed:
        return listed
    try:
        return int(state.get("remaining_ready") or 0)
    except (TypeError, ValueError):
        return 0


def explicit_skip_reason(working: dict[str, Any] | None) -> str | None:
    state = dict(working or {})
    for key in ("ready_skip_reason", "intake_skip_reason", "skip_reason", "reason"):
        value = str(state.get(key) or "").strip()
        if value in EXPLICIT_SKIP_REASONS:
            return value
    for row in list(state.get("actions") or []):
        if not isinstance(row, dict):
            continue
        step = str(row.get("step") or "")
        reason = str(row.get("reason") or "")
        if reason in EXPLICIT_SKIP_REASONS:
            return reason
        if step in {
            "skip_stuck",
            "skip_ready_repo_occupied",
            "skip_ready_open_ai_pr",
            "skip_issue_to_pr_survey_failed",
            "skip_ready_agent_disabled",
            "skip_issue_to_pr_outside_mini_scope",
            "skip_self_product_lane",
            "skip_ready_survey_recent_empty",
        }:
            return reason or step
    return None


def classify_leftover_ready_contract(
    working: dict[str, Any] | None,
) -> dict[str, Any]:
    """Fail closed when leftover ai:ready ends at stamped remaining_ready=0."""
    state = dict(working or {})
    ready_rows = leftover_ready_rows(state)
    if not ready_rows:
        return {
            "ok": True,
            "route": "ok",
            "reason": "no_leftover_ready",
            "leftover_ready": 0,
            "remaining_ready": stamped_remaining_ready(state),
        }
    remaining = stamped_remaining_ready(state)
    if remaining > 0:
        return {
            "ok": True,
            "route": "ok",
            "reason": "ready_filled",
            "leftover_ready": len(ready_rows),
            "remaining_ready": remaining,
        }
    skip = explicit_skip_reason(state)
    if skip:
        return {
            "ok": True,
            "route": "skipped",
            "reason": skip,
            "leftover_ready": len(ready_rows),
            "remaining_ready": 0,
        }
    return {
        "ok": False,
        "route": "contract_broken",
        "reason": "leftover_ai_ready_remaining_ready_zero",
        "error": (
            "leftover row with ai:ready cannot end pass at remaining_ready=0 "
            "without explicit skip reason"
        ),
        "leftover_ready": len(ready_rows),
        "remaining_ready": 0,
    }
