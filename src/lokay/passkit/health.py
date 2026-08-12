"""Honest mill health from remaining counters (pure; no network)."""

from __future__ import annotations

from typing import Any

from lokay.envelope import ok


def health_payload(
    *,
    cfg_mode: str,
    live: bool,
    executed: bool,
    progress: int,
    remaining: dict[str, Any],
    actions: list[dict[str, Any]],
    planned: list[dict[str, Any]],
    stuck_path: str | None,
    executor_enabled: bool,
) -> dict[str, Any]:
    inbox = int(remaining.get("inbox") or 0)
    ready = int(remaining.get("ready") or 0)  # implementable (no open AI PR yet)
    prs = int(
        remaining.get("actionable_open_ai_prs")
        if remaining.get("actionable_open_ai_prs") is not None
        else remaining.get("open_ai_prs") or 0
    )
    mergeable_green = int(remaining.get("mergeable_green") or 0)
    needs_repair = int(remaining.get("needs_repair") or 0)
    survey_errors = int(remaining.get("survey_errors") or 0)
    pending_checks = int(remaining.get("pending_checks") or 0)
    review_limbo = int(remaining.get("review_limbo") or 0)
    repair_actionable = needs_repair if executor_enabled else 0
    # Ready issues need the agent slot when live.
    ready_actionable = ready if (not live or executor_enabled) else 0
    agent_blocked = bool(live and ready > 0 and not executor_enabled)
    # Active repair / CI wait / review limbo are honest non-error waiting states.
    # They must not fingerprint as mill stall → recovery thrash.
    actively_repairing = bool(needs_repair > 0 and (not live or executor_enabled))
    honestly_waiting = bool(
        pending_checks > 0 or review_limbo > 0
    ) and inbox == 0 and ready_actionable == 0 and mergeable_green == 0

    if live:
        actionable_now = inbox + ready_actionable + mergeable_green + repair_actionable
    else:
        actionable_now = inbox + ready + prs

    # Fail-closed: any survey atom failure means we do not know remaining work → not idle.
    idle = inbox == 0 and ready == 0 and prs == 0 and survey_errors == 0
    if survey_errors > 0 and progress == 0:
        health = "survey_error"
    elif idle:
        health = "idle"
    elif progress > 0:
        health = "progress"
    elif not live and (actionable_now > 0 or survey_errors > 0):
        health = "work_remaining"
    elif agent_blocked and progress == 0 and inbox == 0 and mergeable_green == 0:
        # NOT WORKING: ready work exists but agent never runs.
        health = "stall"
    elif actively_repairing and progress == 0:
        # Repair / re-review cycle in flight — waiting on next CI/head move.
        health = "repairing"
    elif honestly_waiting and progress == 0:
        health = "waiting"
    elif actionable_now > 0:
        health = "stall"
    else:
        health = "waiting"

    ok_flag = health not in {"stall", "work_remaining", "survey_error"}
    payload = ok(
        mode=cfg_mode,
        live=live,
        executed=executed,
        planned=planned,
        actions=actions,
        progress=progress,
        remaining=remaining,
        idle=idle,
        health=health,
        stuck_path=stuck_path,
        executor_enabled=executor_enabled,
    )
    if not ok_flag:
        payload["ok"] = False
        if health == "survey_error":
            payload["error"] = (
                f"survey_error: {survey_errors} list atom(s) failed — refuse false idle"
            )
        elif health == "work_remaining":
            payload["error"] = "work_remaining: survey found actionable work (not idle)"
        elif agent_blocked and ready > 0:
            payload["error"] = (
                "stall: ready work remains but executor.enabled is false (agent never runs)"
            )
        else:
            payload["error"] = "stall: actionable work remains but no progress this pass"
    return payload
