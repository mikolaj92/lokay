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
    from lokay.sieve_decision import decision_of
    from lokay.proc.select_issue_do import leftover_of

    decision = decision_of(picked.get("sieve_decision") or {})
    if decision and (decision["repo"], decision["issue"]) == (picked.get("repo"), picked.get("issue")):
        leftover, rows = leftover_of(dict(picked), dict(listed or {}), consume=True)
        return {
            "ok": True, "repo": picked.get("repo"), "issue": picked.get("issue"),
            "route": "do" if decision["route"] == "do" else "skip",
            "reason": decision["reason"], "leftover": leftover, "leftover_issues": rows,
        }
    return select_do(dict(picked), {}, dict(listed or {}))
