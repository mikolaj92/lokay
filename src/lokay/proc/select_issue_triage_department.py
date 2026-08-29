"""Authorize the issue_triage department from the parent switch."""

from __future__ import annotations

from lokay.envelope import ok


def select(*, enabled: bool) -> dict:
    if not enabled:
        return ok(route="skip", reason="issue_triage_disabled")
    return ok(route="run")
