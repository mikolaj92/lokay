"""Authorize the pr_triage department from the parent switch."""

from __future__ import annotations

from lokay.envelope import ok


def select(
    *,
    enabled: bool,
    repair_selected: bool = False,
    executor_selected: bool = False,
    executor_finished: dict | None = None,
) -> dict:
    if repair_selected:
        return ok(route="skip", reason="self_repair_selected")
    if executor_selected and executor_finished is None:
        return ok(route="skip", reason="executor_not_finished")
    if executor_finished is not None and executor_finished.get("ok") is False:
        return ok(route="skip", reason="executor_failed")
    if not enabled:
        return ok(route="skip", reason="pr_triage_disabled")
    return ok(route="run")
