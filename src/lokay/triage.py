"""Deterministic inbox triage: undecided open issue → decision labels.

ai:ready is an *outcome* of triage, not the start of the universe.
Pure rules only — no coding harness.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from lokay.models import Issue

# Substrings (lowercase) that mark out-of-scope inbox items.
OOS_MARKERS = (
    "out of scope",
    "out-of-scope",
    "[oos]",
    "wontfix",
    "won't fix",
    "will not fix",
)

# Title/body heuristics for "enough spec".
MIN_TITLE_LEN = 8
MIN_BODY_LEN = 40
MAX_CHECKBOXES = 5


@dataclass(frozen=True)
class TriageDecision:
    """Result of pure triage for one issue."""

    decision: str  # ready | needs_feedback | out_of_scope | blocked | skip
    reason: str
    add_labels: tuple[str, ...] = ()
    close: bool = False
    comment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Parking labels: not inbox, not implementable (factory keeps milling elsewhere).
PARK_LABELS = frozenset({"frozen", "ai:frozen"})


def decision_labels(
    *,
    ready_label: str = "ai:ready",
    blocked_label: str = "ai:blocked",
    needs_feedback_label: str = "ai:needs-feedback",
    park_labels: Iterable[str] = PARK_LABELS,
) -> frozenset[str]:
    """Labels that mean the issue already left the undecided inbox."""
    return frozenset({ready_label, blocked_label, needs_feedback_label}) | frozenset(park_labels)


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
    """True when issue is intentionally parked (frozen) — skip implement."""
    return bool(set(labels) & frozenset(park_labels))


def _checkbox_count(body: str) -> int:
    return len(re.findall(r"^\s*[-*]\s*\[[ xX]\]", body, flags=re.MULTILINE))


def decide_issue(
    issue: Issue,
    *,
    ready_label: str = "ai:ready",
    blocked_label: str = "ai:blocked",
    needs_feedback_label: str = "ai:needs-feedback",
) -> TriageDecision:
    """Classify one issue. Pure — no I/O."""
    labels = list(issue.labels or [])
    if is_parked(labels):
        return TriageDecision(
            decision="skip",
            reason="parked_frozen",
        )
    if not is_undecided(
        labels,
        ready_label=ready_label,
        blocked_label=blocked_label,
        needs_feedback_label=needs_feedback_label,
    ):
        return TriageDecision(
            decision="skip",
            reason="already_decided",
        )

    title = (issue.title or "").strip()
    body = (issue.body or "").strip()
    blob = f"{title}\n{body}".lower()

    if any(m in blob for m in OOS_MARKERS):
        return TriageDecision(
            decision="out_of_scope",
            reason="oos_marker",
            close=True,
            comment=(
                "Closed as out of scope by Lokay inbox triage "
                f"(marker in title/body). Reopen with a clear in-scope ask if needed."
            ),
        )

    if len(title) < MIN_TITLE_LEN:
        return TriageDecision(
            decision="needs_feedback",
            reason="title_too_short",
            add_labels=(needs_feedback_label,),
            comment=(
                f"Needs feedback: title shorter than {MIN_TITLE_LEN} chars. "
                "Please expand the ask so it can be implemented."
            ),
        )

    if len(body) < MIN_BODY_LEN:
        return TriageDecision(
            decision="needs_feedback",
            reason="body_too_short",
            add_labels=(needs_feedback_label,),
            comment=(
                f"Needs feedback: body shorter than {MIN_BODY_LEN} chars. "
                "Add acceptance criteria / expected behavior."
            ),
        )

    boxes = _checkbox_count(body)
    if boxes > MAX_CHECKBOXES or re.search(r"\bepic\b", blob):
        return TriageDecision(
            decision="needs_feedback",
            reason="too_large_split",
            add_labels=(needs_feedback_label,),
            comment=(
                "Needs feedback: issue looks too large for one AI pass "
                f"(checkboxes={boxes}). Please split into smaller issues."
            ),
        )

    return TriageDecision(
        decision="ready",
        reason="spec_ok",
        add_labels=(ready_label,),
        comment=None,
    )
