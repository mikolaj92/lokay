"""Authorize the self_repair department after last-pass motion + switch."""

from __future__ import annotations

from lokay.envelope import ok


def select(*, enabled: bool, moved_forward: bool, receipt_present: bool = True) -> dict:
    if not enabled:
        return ok(route="skip", reason="self_repair_disabled")
    if not receipt_present:
        return ok(route="skip", reason="stale_receipt")
    if moved_forward:
        return ok(route="skip", reason="last_pass_moved")
    return ok(route="run", reason="did_not_move")
