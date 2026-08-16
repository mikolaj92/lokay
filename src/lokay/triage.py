"""Deterministic inbox triage: undecided open issue → decision labels.

ai:ready is an *outcome* of triage, not the start of the universe.
Pure rules only — no coding harness.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from lokay.issue_checkboxes import work_checkbox_count
from lokay.models import Issue
from lokay.stage_ledger import LEDGER_ACTIVE_LABELS

# Title markers for whole-issue OOS (substring match on title only).
OOS_TITLE_MARKERS = (
    "out of scope",
    "out-of-scope",
    "[oos]",
    "wontfix",
    "won't fix",
    "will not fix",
)

# Explicit whole-issue status in body (not section headings).
_OOS_STATUS_LINE = re.compile(
    r"(?im)^\s*(?:status|decision)\s*:\s*out[\s-]*of[\s-]*scope\b"
)
_OOS_STANDALONE = re.compile(
    r"(?im)^\s*(?:\[oos\]|out[\s-]*of[\s-]*scope|wontfix|won't fix|will not fix)\s*$"
)
_OOS_INLINE_TAG = re.compile(r"(?i)\[oos\]")
_WONTFIX = re.compile(r"(?i)\b(?:wontfix|won't fix|will not fix)\b")

# Strip non-goal sections so "Out of scope" headings never close real bugs.
_NONGOAL_SECTION = re.compile(
    r"(?ims)^#{1,6}\s*(?:"
    r"out\s*of\s*scope|out-of-scope|non-?goals|not\s+in\s+(?:this\s+)?scope|"
    r"explicitly\s+not\s+in\s+this\s+issue"
    r")\s*\n.*?(?=^#{1,6}\s|\Z)"
)

# Title/body heuristics for "enough spec".
MIN_TITLE_LEN = 8
MIN_BODY_LEN = 40
MAX_CHECKBOXES = 5


@dataclass(frozen=True)
class TriageDecision:
    """Result of pure triage for one issue."""

    decision: str  # ready | needs_feedback | split | out_of_scope | blocked | skip
    reason: str
    add_labels: tuple[str, ...] = ()
    close: bool = False
    comment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Parking labels: not inbox, not implementable (factory keeps milling elsewhere).
# ai:tracker = auto-split parent; mill continues other work (human mailbox only).
PARK_LABELS = frozenset({"frozen", "ai:frozen", "ai:tracker"})


def decision_labels(
    *,
    ready_label: str = "ai:ready",
    blocked_label: str = "ai:blocked",
    needs_feedback_label: str = "ai:needs-feedback",
    park_labels: Iterable[str] = PARK_LABELS,
) -> frozenset[str]:
    """Labels that mean the issue already left the undecided inbox."""
    # Leftover in-flight cache must not bounce the issue back into inbox.
    return (
        frozenset({ready_label, blocked_label, needs_feedback_label})
        | frozenset(park_labels)
        | LEDGER_ACTIVE_LABELS
    )


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
    return work_checkbox_count(body)


def _strip_nongoal_sections(body: str) -> str:
    """Remove markdown sections that list non-goals (not issue status)."""
    return _NONGOAL_SECTION.sub("", body or "")


def _is_out_of_scope(title: str, body: str) -> bool:
    """Whole-issue OOS only — never ## Out of scope non-goal sections.

    True when:
    - title contains an OOS marker, or
    - body (after stripping non-goal sections) has explicit status/decision
      line, standalone OOS line, [oos] tag, or wontfix wording.
    """
    title_l = (title or "").lower()
    if any(m in title_l for m in OOS_TITLE_MARKERS):
        return True

    rest = _strip_nongoal_sections(body or "")
    if _OOS_STATUS_LINE.search(rest):
        return True
    if _OOS_STANDALONE.search(rest):
        return True
    if _OOS_INLINE_TAG.search(rest):
        return True
    if _WONTFIX.search(rest):
        return True
    return False


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

    if _is_out_of_scope(title, body):
        return TriageDecision(
            decision="out_of_scope",
            reason="oos_marker",
            close=True,
            comment=(
                "Closed as out of scope by Lokay inbox triage "
                "(explicit OOS marker in title or status — not a Non-goals section). "
                "Reopen with a clear in-scope ask if needed."
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
    # "epic" only in TITLE means the whole issue is an epic tracker.
    # Body phrases like "Parent epic" / "child of epic" must NOT block implementable issues
    # (Pad Audit wave: 362 false needs-feedback from "## Parent epic" footers).
    # Oversized work → SPLIT (auto child issues), not needs-feedback brake.
    title_is_epic = bool(re.search(r"\bepic\b", title.lower()))
    if boxes > MAX_CHECKBOXES or title_is_epic:
        return TriageDecision(
            decision="split",
            reason="too_large_split",
            add_labels=(),
            comment=None,
        )

    return TriageDecision(
        decision="ready",
        reason="spec_ok",
        add_labels=(ready_label,),
        comment=None,
    )
