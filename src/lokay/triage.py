"""Deterministic inbox triage: undecided open issue → decision labels.

ai:ready is an *outcome* of triage, not the start of the universe.
Pure rules only — no coding harness.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

from lokay.models import Issue
from lokay.stage_ledger import LABEL_WORK_READY, LEDGER_ACTIVE_LABELS

_PREFLIGHT_MARKER = re.compile(r"<!--\s*lokay-preflight:[0-9a-fA-F]+\s*-->")
_PREFLIGHT_TITLE = re.compile(r"(?i)^preflight failure\b")

# Title/body length is mechanical. Prose classification belongs to the agent.
MIN_TITLE_LEN = 8
MIN_BODY_LEN = 40


@dataclass(frozen=True)
class TriageDecision:
    """Result of pure triage for one issue."""

    decision: str  # ready | skip | split | out_of_scope | blocked
    reason: str
    add_labels: tuple[str, ...] = ()
    close: bool = False
    comment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Tracker = auto-split parent; lokay continues other work.
# ai:frozen / needs-feedback / blocked are NOT durable process state — stale
# limbo labels re-enter triage. Legal exits: ready | split | skip | close.
MACHINE_PARK_LABEL = "ai:frozen"  # legacy name; never stamp on issues
PARK_LABELS = frozenset({"ai:tracker"})
LIMBO_LABELS = frozenset({"frozen", "ai:frozen", "ai:needs-feedback", "ai:blocked"})


def decision_labels(
    *,
    ready_label: str = "ai:ready",
    blocked_label: str = "ai:blocked",
    needs_feedback_label: str = "ai:needs-feedback",
    park_labels: Iterable[str] = PARK_LABELS,
) -> frozenset[str]:
    """Labels that mean the issue already left the undecided inbox.

    Stale limbo labels (frozen / blocked / needs-feedback) are *not* permanent
    decisions — they re-enter triage so the factory can skip/split/close.
    """
    # Params kept for call-site compat; limbo is not a decided state.
    _ = (blocked_label, needs_feedback_label)
    # Leftover in-flight cache must not bounce the issue back into inbox.
    return frozenset({ready_label}) | frozenset(park_labels) | LEDGER_ACTIVE_LABELS


def is_undecided(
    labels: Iterable[str],
    *,
    ready_label: str = "ai:ready",
    blocked_label: str = "ai:blocked",
    needs_feedback_label: str = "ai:needs-feedback",
    park_labels: Iterable[str] = PARK_LABELS,
) -> bool:
    decided = decision_labels(
        ready_label=ready_label,
        blocked_label=blocked_label,
        needs_feedback_label=needs_feedback_label,
        park_labels=park_labels,
    )
    return not (set(labels) & decided)


def is_parked(labels: Iterable[str], *, park_labels: Iterable[str] = PARK_LABELS) -> bool:
    """True when issue is an auto-split tracker parent — skip implement."""
    return bool(set(labels) & frozenset(park_labels))


def is_human_stopped(
    labels: Iterable[str],
    *,
    blocked_label: str = "ai:blocked",
    needs_feedback_label: str = "ai:needs-feedback",
    park_labels: Iterable[str] = PARK_LABELS,
) -> bool:
    """Human stop labels exclude work. They do not admit it."""
    have = set(labels)
    return bool(
        have
        & (
            frozenset({blocked_label, needs_feedback_label})
            | frozenset(park_labels)
        )
    )


def is_open_work_issue(
    labels: Iterable[str],
    *,
    state: str = "OPEN",
    blocked_label: str = "ai:blocked",
    needs_feedback_label: str = "ai:needs-feedback",
    park_labels: Iterable[str] = PARK_LABELS,
) -> bool:
    """Open catalog issue is work unless a human stop excludes it.

    Ready labels (`ai:ready` / `ready-for-agent`) are the start ticket for
    implement. This helper is open-minus-human-stop hygiene, not intake.
    """
    if str(state or "OPEN").upper() == "CLOSED":
        return False
    return not is_human_stopped(
        labels,
        blocked_label=blocked_label,
        needs_feedback_label=needs_feedback_label,
        park_labels=park_labels,
    )


def is_preflight_incident(*, title: str, body: str) -> bool:
    """True when GitHub issue is a lokay preflight incident, not product work."""
    if _PREFLIGHT_MARKER.search(body or ""):
        return True
    return bool(_PREFLIGHT_TITLE.search((title or "").strip()))


def decide_issue(
    issue: Issue,
    *,
    ready_label: str = "ai:ready",
    blocked_label: str = "ai:blocked",
    needs_feedback_label: str = "ai:needs-feedback",
) -> TriageDecision:
    """Classify one issue. Pure — no I/O."""
    title = (issue.title or "").strip()
    body = (issue.body or "").strip()

    if is_preflight_incident(title=title, body=body):
        return TriageDecision(
            decision="skip",
            reason="preflight_incident",
            add_labels=(),
            comment=(
                "Skipped (factory): lokay preflight incident. Self-repair owns this, "
                "not issue_to_pr. No limbo label — issue stays open in queue."
            ),
        )

    if len(title) < MIN_TITLE_LEN:
        return TriageDecision(
            decision="skip",
            reason="title_too_short",
            add_labels=(),
            comment=(
                f"Skipped (factory): title shorter than {MIN_TITLE_LEN} chars. "
                "No limbo label — expand the ask, split, or leave open for later."
            ),
        )

    if len(body) < MIN_BODY_LEN:
        return TriageDecision(
            decision="skip",
            reason="body_too_short",
            add_labels=(),
            comment=(
                f"Skipped (factory): body shorter than {MIN_BODY_LEN} chars. "
                "No limbo label — add acceptance criteria, split, or leave open for later."
            ),
        )

    return TriageDecision(
        decision="ready",
        reason="spec_ok",
        add_labels=(),
        comment=None,
    )
