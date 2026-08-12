"""Issue-as-live-ledger: exclusive stage labels operators can read like chat.

GitHub Issues are the visible conversation with the mill. Each major Fala stage
swaps one exclusive ledger label (plus optional short receipt). Hermetic helpers
only — no network.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

# Reuse existing labels where they already mean the stage.
LABEL_READY = "ai:ready"
LABEL_IMPLEMENTING = "ai:in-progress"  # unused historically; now "implementing"
LABEL_PR_OPEN = "ai:pr-open"  # issue-side; PR chrome stays ai:pr-opened
LABEL_CI_WAITING = "ai:ci-waiting"
LABEL_REPAIRING = "ai:repairing"

# New issue ledger labels (≤6). ready + in-progress already exist in _LABEL_META.
NEW_LEDGER_LABELS: tuple[str, ...] = (
    LABEL_PR_OPEN,
    LABEL_CI_WAITING,
    LABEL_REPAIRING,
)

# Active in-flight stages (left inbox; not implementable as ready).
LEDGER_ACTIVE_LABELS: frozenset[str] = frozenset(
    {
        LABEL_IMPLEMENTING,
        LABEL_PR_OPEN,
        LABEL_CI_WAITING,
        LABEL_REPAIRING,
    }
)

STAGES: frozenset[str] = frozenset(
    {
        "ready",
        "implementing",
        "pr-open",
        "ci-waiting",
        "repairing",
        "clear",
    }
)

_RECEIPTS: dict[str, str] = {
    "ready": "Lokay ledger: ready for implement.",
    "implementing": "Lokay ledger: implementing (issue_to_pr).",
    "pr-open": "Lokay ledger: PR open.",
    "ci-waiting": "Lokay ledger: waiting on CI checks.",
    "repairing": "Lokay ledger: repairing PR (pr_repair).",
    "clear": "Lokay ledger: stage cleared after merge/close.",
}


@dataclass(frozen=True)
class StagePlan:
    """Exclusive label swap for one ledger stage."""

    stage: str
    add_labels: tuple[str, ...]
    remove_labels: tuple[str, ...]
    receipt: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def ledger_labels(*, ready_label: str = LABEL_READY) -> frozenset[str]:
    """All labels that participate in the exclusive issue ledger."""
    return frozenset({ready_label}) | LEDGER_ACTIVE_LABELS


def plan_stage_transition(
    stage: str,
    *,
    ready_label: str = LABEL_READY,
    receipt: bool = False,
) -> StagePlan:
    """Pure transition: set one stage, remove the other ledger labels."""
    name = str(stage or "").strip().lower()
    if name not in STAGES:
        raise ValueError(
            f"unknown ledger stage {stage!r}; expected one of {sorted(STAGES)}"
        )
    all_ledger = ledger_labels(ready_label=ready_label)
    add: tuple[str, ...]
    if name == "ready":
        add = (ready_label,)
    elif name == "implementing":
        add = (LABEL_IMPLEMENTING,)
    elif name == "pr-open":
        add = (LABEL_PR_OPEN,)
    elif name == "ci-waiting":
        add = (LABEL_CI_WAITING,)
    elif name == "repairing":
        add = (LABEL_REPAIRING,)
    else:  # clear
        add = ()
    remove = tuple(sorted(lab for lab in all_ledger if lab not in add))
    note = _RECEIPTS.get(name) if receipt else None
    return StagePlan(stage=name, add_labels=add, remove_labels=remove, receipt=note)


def current_ledger_stage(
    labels: Iterable[str],
    *,
    ready_label: str = LABEL_READY,
) -> str | None:
    """Best-effort stage from current labels (exclusive preference order)."""
    have = set(labels)
    for stage, label in (
        ("repairing", LABEL_REPAIRING),
        ("ci-waiting", LABEL_CI_WAITING),
        ("pr-open", LABEL_PR_OPEN),
        ("implementing", LABEL_IMPLEMENTING),
        ("ready", ready_label),
    ):
        if label in have:
            return stage
    return None
