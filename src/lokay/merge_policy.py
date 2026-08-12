"""Trusted auto-merge decision matrix (pure, hermetic).

Product law: once an AI PR is green and policy-approved, merge without a
person. Fail closed on secrets, needs_human, escalated needs-review, and
terminal ``ai:needs-review`` labels.

Actions:
  merge     — execute pr_merge (+ close_issue when graph continues)
  waiting   — pending CI or no-CI while require_checks (not stall, not human)
  repair    — red checks or repairable request_changes
  blocked   — human/security/policy terminal (never auto-merge)
  disabled  — merge.enabled off
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

MergeAction = Literal["merge", "waiting", "repair", "blocked", "disabled"]

# Reasons that mean "honest wait" (CI / policy gate), not human mailbox.
WAITING_REASONS = frozenset(
    {
        "checks_pending",
        "checks_none_require_checks",
        "merge_disabled",
    }
)

# Tick / status remaining fields for WAITING_REASONS — one matrix for organ + fleet.
WAITING_REMAINING_FIELDS: Mapping[str, str] = {
    "checks_pending": "pending_checks",
    "checks_none_require_checks": "no_checks_blocked",
    "merge_disabled": "merge_disabled",
}

NEEDS_REVIEW_REASONS = frozenset(
    {
        "secrets",
        "needs_human",
        "llm_review_escalated_needs_review",
        "ai_needs_review_label",
        "invalid_review_json",
    }
)


def soft_waiting_remaining(remaining: Mapping[str, Any]) -> int:
    """Sum soft merge_policy wait counters from a tick remaining map."""
    total = 0
    for reason in WAITING_REASONS:
        field = WAITING_REMAINING_FIELDS.get(reason)
        if field is None:
            continue
        total += int(remaining.get(field) or 0)
    return total


def actionable_mergeable_green(
    remaining: Mapping[str, Any], *, merge_enabled: bool
) -> int:
    """Green PRs the mill can merge this pass (excludes merge_disabled soft wait).

    When ``merge.enabled`` is false, green PRs are honest waiting — not stall
    actionable. Prefer an explicit ``merge_disabled`` remaining count; fall back
    to treating all ``mergeable_green`` as waiting when merge is disarmed.
    """
    green = int(remaining.get("mergeable_green") or 0)
    if green <= 0:
        return 0
    if not merge_enabled:
        return 0
    disabled = int(remaining.get("merge_disabled") or 0)
    return max(0, green - disabled)


@dataclass(frozen=True)
class AutoMergeDecision:
    action: MergeAction
    reason: str
    merge_ok: bool = False
    repairable: bool = False
    waiting: bool = False
    needs_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "merge_ok": self.merge_ok,
            "repairable": self.repairable,
            "waiting": self.waiting,
            "needs_review": self.needs_review,
        }


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _label_names(labels: Any) -> list[str]:
    if not isinstance(labels, list):
        return []
    out: list[str] = []
    for item in labels:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, Mapping) and isinstance(item.get("name"), str):
            name = item["name"].strip()
            if name:
                out.append(name)
    return out


def _checks_mergeable(
    checks: Mapping[str, Any], *, require_checks: bool
) -> tuple[bool, str | None, MergeAction | None]:
    """Return (mergeable, reason_if_not, action_if_not)."""
    status = str(checks.get("status") or "").strip().lower()
    if checks.get("merge_ok") is True or checks.get("green") is True or status == "passed":
        return True, None, None
    if status == "pending":
        return False, "checks_pending", "waiting"
    if status == "failed":
        return False, "checks_failed", "repair"
    if status == "none":
        if require_checks and not checks.get("merge_ok"):
            return False, "checks_none_require_checks", "waiting"
        # No CI and policy allows it.
        return True, None, None
    if status == "offline":
        # Offline survey: do not merge live; wait for a real checks read.
        return False, "checks_offline", "waiting"
    if status in {"", "unknown"} and not checks:
        # Empty upstream (dry-run / missing conduction): do not invent green.
        return False, "checks_missing", "waiting"
    return False, "checks_not_mergeable", "blocked"


def _review_gate(
    review: Mapping[str, Any], *, require_llm_review: bool
) -> AutoMergeDecision | None:
    """Return a blocking/waiting/repair decision, or None when review allows merge."""
    if not require_llm_review:
        return None

    if not review:
        return AutoMergeDecision(
            action="blocked",
            reason="llm_review_missing",
            needs_review=False,
        )

    decision = _as_mapping(review.get("decision"))
    verdict = str(decision.get("verdict") or "").strip().lower()
    secrets = bool(decision.get("secrets"))
    escalated = bool(review.get("escalated"))
    merge_ok = bool(review.get("merge_ok"))

    if secrets:
        return AutoMergeDecision(
            action="blocked",
            reason="secrets",
            needs_review=True,
        )
    if escalated or review.get("reason") == "llm_review_escalated_needs_review":
        return AutoMergeDecision(
            action="blocked",
            reason="llm_review_escalated_needs_review",
            needs_review=True,
        )
    if verdict == "needs_human":
        return AutoMergeDecision(
            action="blocked",
            reason="needs_human",
            needs_review=True,
        )

    skip_reason = str(review.get("reason") or "")
    if (
        not merge_ok
        and review.get("skipped")
        and skip_reason
        in {
            "executor_disabled",
            "invalid_review_json",
            "llm_review_requires_executor",
        }
    ):
        return AutoMergeDecision(
            action="blocked",
            reason=skip_reason,
            needs_review=skip_reason == "invalid_review_json",
        )

    if verdict == "request_changes":
        repairable = not secrets and not escalated
        return AutoMergeDecision(
            action="repair" if repairable else "blocked",
            reason=(
                "llm_review_requested_changes"
                if repairable
                else "llm_review_not_approved"
            ),
            repairable=repairable,
            needs_review=not repairable,
        )

    if merge_ok and (
        verdict == "approve"
        or skip_reason == "llm_review_not_required"
        or (
            review.get("skipped")
            and skip_reason == "already_reviewed_head"
            and verdict in {"", "approve"}
        )
    ):
        return None

    if merge_ok and verdict == "" and not decision:
        # Bypass payload (llm_review_not_required) or marker-only approve.
        return None

    if not merge_ok:
        return AutoMergeDecision(
            action="blocked",
            reason="llm_review_not_approved",
            needs_review=False,
        )

    # merge_ok set but verdict inconsistent — fail closed.
    return AutoMergeDecision(
        action="blocked",
        reason="llm_review_inconsistent",
        needs_review=True,
    )


def decide_auto_merge(
    *,
    merge_enabled: bool,
    require_checks: bool = False,
    require_llm_review: bool = True,
    checks: Mapping[str, Any] | None = None,
    review: Mapping[str, Any] | None = None,
    pr_labels: Any = None,
) -> AutoMergeDecision:
    """Decide whether an AI PR may auto-merge under trusted policy."""
    if not merge_enabled:
        return AutoMergeDecision(
            action="disabled",
            reason="merge_disabled",
            waiting=True,
        )

    labels = _label_names(pr_labels)
    if "ai:needs-review" in labels:
        return AutoMergeDecision(
            action="blocked",
            reason="ai_needs_review_label",
            needs_review=True,
        )

    checks_m = _as_mapping(checks)
    mergeable, checks_reason, checks_action = _checks_mergeable(
        checks_m, require_checks=require_checks
    )
    if not mergeable:
        assert checks_reason and checks_action
        return AutoMergeDecision(
            action=checks_action,
            reason=checks_reason,
            repairable=checks_action == "repair",
            waiting=checks_action == "waiting",
            needs_review=False,
        )

    blocked = _review_gate(_as_mapping(review), require_llm_review=require_llm_review)
    if blocked is not None:
        return blocked

    return AutoMergeDecision(action="merge", reason="approve_green", merge_ok=True)
