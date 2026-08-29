"""Authorize the self_repair department after last-pass motion + leftover + switch."""

from __future__ import annotations

from lokay.envelope import ok


def leftover_gate(*, leftover_skip: bool) -> dict:
    """Leftover overflow is not a stall and must not start machine repair."""
    if leftover_skip:
        return ok(route="skip", reason="leftover_skip")
    return ok(route="run", reason="not_leftover")


def select(
    *,
    enabled: bool,
    moved_forward: bool,
    receipt_present: bool = True,
    leftover_skip: bool = False,
) -> dict:
    if not enabled:
        return ok(route="skip", reason="self_repair_disabled")
    leftover = leftover_gate(leftover_skip=leftover_skip)
    if leftover["route"] == "skip":
        return leftover
    if not receipt_present:
        return ok(route="skip", reason="stale_receipt")
    if moved_forward:
        return ok(route="skip", reason="last_pass_moved")
    return ok(route="run", reason="did_not_move")
