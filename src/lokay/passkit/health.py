"""Honest lokay health from remaining counters (pure; no network)."""

from __future__ import annotations

from typing import Any

from lokay.envelope import ok
from lokay.merge_policy import actionable_mergeable_green, soft_waiting_remaining


def implementable_ready(remaining: dict[str, Any], *, live: bool, executor_enabled: bool) -> int:
    """Ready tickets the lokay can start this pass.

    ``remaining.ready`` is the survey catalog. Per-repo PR-first and occupancy
    freeze that catalog until closeout / the live job finishes — those rows
    are waiting, not stall bait.
    """
    ready = int(remaining.get("ready") or 0)
    if live and not executor_enabled:
        return 0
    by_repo = remaining.get("by_repo")
    if not isinstance(by_repo, list) or not by_repo:
        return ready
    implementable = 0
    frozen = 0
    for row in by_repo:
        if not isinstance(row, dict):
            continue
        n = int(row.get("ready") or 0)
        actionable_prs = int(row.get("actionable_open_ai_prs") or 0)
        if actionable_prs > 0 or bool(row.get("occupied")):
            frozen += n
        else:
            implementable += n
    if implementable + frozen == ready:
        return implementable
    return max(0, ready - frozen)


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
    merge_enabled: bool = True,
) -> dict[str, Any]:
    inbox = int(remaining.get("inbox") or 0)
    ready = int(remaining.get("ready") or 0)  # implementable (no open AI PR yet)
    started = int(remaining.get("issue_to_pr_started") or 0)
    # Detached issue_to_pr is real work this pass. Count it even when the
    # progress counter was snapshotted before dispatch wrote working.json.
    if started > 0:
        progress = max(int(progress), started)
    prs = int(
        remaining.get("actionable_open_ai_prs")
        if remaining.get("actionable_open_ai_prs") is not None
        else remaining.get("open_ai_prs") or 0
    )
    needs_repair = int(remaining.get("needs_repair") or 0)
    survey_errors = int(remaining.get("survey_errors") or 0)
    review_limbo = int(remaining.get("review_limbo") or 0)
    if remaining.get("manual_open_ai_prs") is not None:
        manual_prs = int(remaining.get("manual_open_ai_prs") or 0)
    else:
        # Legacy receipts: parked PRs were folded into open_ai_prs.
        open_all = int(remaining.get("open_ai_prs") or 0)
        manual_prs = max(0, open_all - prs)
    # Same matrix as merge_policy WAITING_REASONS (pending / no-CI / merge off).
    mergeable_now = actionable_mergeable_green(
        remaining, merge_enabled=merge_enabled
    )
    soft_waits = soft_waiting_remaining(remaining)
    # Legacy receipts: merge off + green with no merge_disabled field yet.
    if not merge_enabled and int(remaining.get("mergeable_green") or 0) > 0:
        soft_waits = max(
            soft_waits, int(remaining.get("mergeable_green") or 0)
        )
    repair_actionable = needs_repair if executor_enabled else 0
    # Ready catalog is not stall bait when every remaining ticket sits in a
    # PR-first / occupied repo (closeout owns the lane; next pass implements).
    ready_actionable = implementable_ready(
        remaining, live=live, executor_enabled=executor_enabled
    )
    # Disabled agent is still a stall even when the catalog is PR-first frozen.
    agent_blocked = bool(live and ready > 0 and not executor_enabled)
    # Active repair / CI wait / review limbo / parked needs-review / merge-disarmed
    # green are honest non-error waiting states. They must not fingerprint as stall.
    actively_repairing = bool(needs_repair > 0 and (not live or executor_enabled))
    honestly_waiting = bool(
        soft_waits > 0 or review_limbo > 0 or manual_prs > 0
    ) and inbox == 0 and ready_actionable == 0 and mergeable_now == 0

    if live:
        actionable_now = inbox + ready_actionable + mergeable_now + repair_actionable
    else:
        actionable_now = inbox + ready + prs

    # Fail-closed: any survey atom failure means we do not know remaining work → not idle.
    # Parked ai:needs-review PRs are a human mailbox, not empty-queue idle.
    idle = (
        inbox == 0
        and ready == 0
        and prs == 0
        and manual_prs == 0
        and review_limbo == 0
        and survey_errors == 0
    )
    if survey_errors > 0 and progress == 0:
        health = "survey_error"
    elif idle:
        health = "idle"
    elif progress > 0:
        health = "progress"
    elif not live and (actionable_now > 0 or survey_errors > 0):
        health = "work_remaining"
    elif agent_blocked and progress == 0 and inbox == 0 and mergeable_now == 0:
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
        merge_enabled=merge_enabled,
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


def evaluate_lokay_stop(tick: dict[str, Any]) -> dict[str, Any]:
    """Stop rules for compose_run. Lives with health, not the lokay loop.

    ``hard`` means the lokay envelope is ok=false (stall/survey_error).
    ``plateau`` stops the loop but is not a stall fingerprint.
    """
    health = str(tick.get("health") or "")
    if health == "host_updated" or str(tick.get("reason") or "") == "host_updated":
        return {
            "stop": True,
            "hard": False,
            "health": "host_updated",
            "error": "",
        }
    if health in {"stall", "survey_error"}:
        return {
            "stop": True,
            "hard": True,
            "health": health,
            "error": f"lokay {health}: actionable work remains but no real progress",
        }
    if health == "plateau":
        return {
            "stop": True,
            "hard": True,
            "health": "plateau",
            "error": "lokay plateau: progress claimed but remaining work unchanged (green noop)",
        }
    if not tick.get("ok") and health not in {"waiting", "repairing", "progress", "running", "idle"}:
        return {
            "stop": True,
            "hard": True,
            "health": health or "failed",
            "error": str(tick.get("error") or "lokay pass failed"),
        }
    if int(tick.get("progress") or 0) == 0 and not tick.get("idle"):
        return {
            "stop": True,
            "hard": False,
            "health": health or "waiting",
            "error": "",
        }
    return {"stop": False, "hard": False, "health": health, "error": ""}
