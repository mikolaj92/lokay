"""Issue ledger: decisions only. In-flight is a fact, not a label.

Hermetic helpers only — no network. Fala still calls stage names
(`implementing` / `pr-open` / …); those plans strip leftover cache and
keep `ai:ready`. Mutex is the live job or covering open PR.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

LABEL_READY = "ai:ready"
# Retired cache. Still stripped by stage/reap; never awarded.
LABEL_IMPLEMENTING = "ai:in-progress"
LABEL_PR_OPEN = "ai:pr-open"
LABEL_CI_WAITING = "ai:ci-waiting"
LABEL_REPAIRING = "ai:repairing"

NEW_LEDGER_LABELS: tuple[str, ...] = ()

# Leftover in-flight cache: not inbox, reap restores ready.
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

INFLIGHT_STAGES: frozenset[str] = frozenset(
    {"implementing", "pr-open", "ci-waiting", "repairing"}
)

_RECEIPTS: dict[str, str] = {
    "ready": "Lokay ledger: ready for implement.",
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
    # In-flight names stay in the Fala DAG but must not mint cache or drop ready.
    if name in INFLIGHT_STAGES:
        name = "ready"
    all_ledger = ledger_labels(ready_label=ready_label)
    add: tuple[str, ...]
    if name == "ready":
        add = (ready_label,)
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
