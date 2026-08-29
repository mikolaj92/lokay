"""Pick the next ready/"do" issue for the executor. Not a sieve. Not a merge."""

from __future__ import annotations

from typing import Any, Mapping

from lokay.proc.select_issue_do import select as select_do
from lokay.proc.select_next_issue import select as select_next


def pick(listed: Mapping[str, Any], last: Mapping[str, Any] | None = None) -> dict:
    """First block: one takeable row. Foreign assignees are already skipped."""
    return select_next(dict(listed), dict(last or {}))


def select(picked: Mapping[str, Any], listed: Mapping[str, Any] | None = None) -> dict:
    """Second block: ready leftover becomes do. No triage. No merge."""
    return select_do(dict(picked), {}, dict(listed or {}))
