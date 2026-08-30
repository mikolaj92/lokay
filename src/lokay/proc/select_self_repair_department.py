"""Authorize the self_repair department after last-pass motion + leftover + switch.

One pass is oil XOR product (product wins). Idle, pass_ceiling, occupied,
leftover skip, and empty survey are not stalls. Only did_not_move starts oil.
The exclusions match select_repair_route.
"""

from __future__ import annotations

from typing import Any

from lokay.envelope import ok
from lokay.proc.select_repair_route import classify as classify_repair_route


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
    receipt: dict[str, Any] | None = None,
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
    if receipt is not None:
        routed = classify_repair_route(receipt)
        if str(routed.get("route") or "") != "repair":
            return ok(
                route="skip",
                reason=str(routed.get("reason") or "not_stall"),
            )
    return ok(route="run", reason="did_not_move")
