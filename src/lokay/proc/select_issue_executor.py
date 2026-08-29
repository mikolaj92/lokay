"""Authorize issue_to_pr launch after sito + executor department switch."""

from __future__ import annotations

from typing import Any, Mapping

from lokay.envelope import ok


def select(picked: Mapping[str, Any], *, enabled: bool) -> dict[str, Any]:
    reason = str(picked.get("reason") or "no_work")
    base = {
        "repo": picked.get("repo"),
        "issue": picked.get("issue"),
        "leftover": picked.get("leftover"),
        "leftover_issues": list(picked.get("leftover_issues") or []),
    }
    if str(picked.get("route") or "") != "do":
        return ok(route="skip", reason=reason, **base)
    if not enabled:
        return ok(route="skip", reason="executor_disabled", **base)
    return ok(route="do", **base)
