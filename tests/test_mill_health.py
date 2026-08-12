"""Health rules: no green noop while work remains."""

from lokay.merge_policy import (
    WAITING_REASONS,
    WAITING_REMAINING_FIELDS,
    actionable_mergeable_green,
    decide_auto_merge,
    soft_waiting_remaining,
)
from lokay.passkit.health import health_payload as _health_payload


def test_survey_work_remaining_fails_ok():
    payload = _health_payload(
        cfg_mode="dry-run",
        live=False,
        executed=False,
        progress=0,
        remaining={
            "inbox": 1,
            "ready": 0,
            "open_ai_prs": 0,
            "mergeable_green": 0,
            "needs_repair": 0,
        },
        actions=[],
        planned=[],
        stuck_path=None,
        executor_enabled=False,
    )
    assert payload["health"] == "work_remaining"
    assert payload["ok"] is False
    assert payload["idle"] is False


def test_idle_when_empty():
    payload = _health_payload(
        cfg_mode="live",
        live=True,
        executed=True,
        progress=0,
        remaining={
            "inbox": 0,
            "ready": 0,
            "open_ai_prs": 0,
            "mergeable_green": 0,
            "needs_repair": 0,
        },
        actions=[],
        planned=[],
        stuck_path="/tmp/stuck.json",
        executor_enabled=True,
    )
    assert payload["health"] == "idle"
    assert payload["ok"] is True
    assert payload["idle"] is True


def test_live_stall_when_ready_no_progress():
    payload = _health_payload(
        cfg_mode="live",
        live=True,
        executed=True,
        progress=0,
        remaining={
            "inbox": 0,
            "ready": 2,
            "open_ai_prs": 0,
            "mergeable_green": 0,
            "needs_repair": 0,
        },
        actions=[],
        planned=[],
        stuck_path=None,
        executor_enabled=True,
    )
    assert payload["health"] == "stall"
    assert payload["ok"] is False


def test_live_stall_when_ready_but_agent_disabled():
    payload = _health_payload(
        cfg_mode="live",
        live=True,
        executed=True,
        progress=0,
        remaining={
            "inbox": 0,
            "ready": 1,
            "open_ai_prs": 0,
            "mergeable_green": 0,
            "needs_repair": 0,
        },
        actions=[],
        planned=[],
        stuck_path=None,
        executor_enabled=False,
    )
    assert payload["health"] == "stall"
    assert payload["ok"] is False
    assert "executor.enabled" in str(payload.get("error") or "")


def test_live_waiting_when_only_open_prs_not_actionable():
    """Conflicts closed or only pending: no stall if nothing mergeable/repairable."""
    payload = _health_payload(
        cfg_mode="live",
        live=True,
        executed=True,
        progress=0,
        remaining={
            "inbox": 0,
            "ready": 0,
            "open_ai_prs": 1,
            "mergeable_green": 0,
            "needs_repair": 0,
        },
        actions=[],
        planned=[],
        stuck_path=None,
        executor_enabled=True,
    )
    assert payload["health"] == "waiting"
    assert payload["ok"] is True
    assert payload["idle"] is False


def test_live_repairing_when_needs_repair_not_stall():
    payload = _health_payload(
        cfg_mode="live",
        live=True,
        executed=True,
        progress=0,
        remaining={
            "inbox": 0,
            "ready": 0,
            "open_ai_prs": 1,
            "mergeable_green": 1,
            "needs_repair": 1,
        },
        actions=[{"step": "pr_review_repair"}],
        planned=[],
        stuck_path=None,
        executor_enabled=True,
    )
    assert payload["health"] == "repairing"
    assert payload["ok"] is True
    assert payload["idle"] is False


def test_live_waiting_when_review_limbo_only():
    payload = _health_payload(
        cfg_mode="live",
        live=True,
        executed=True,
        progress=0,
        remaining={
            "inbox": 0,
            "ready": 0,
            "open_ai_prs": 1,
            "mergeable_green": 0,
            "needs_repair": 0,
            "review_limbo": 1,
            "pending_checks": 0,
        },
        actions=[],
        planned=[],
        stuck_path=None,
        executor_enabled=True,
    )
    assert payload["health"] == "waiting"
    assert payload["ok"] is True


def test_live_waiting_when_green_but_merge_disabled():
    """Green + merge.enabled false is mill ok-stop waiting, not false stall."""
    remaining = {
        "inbox": 0,
        "ready": 0,
        "open_ai_prs": 1,
        "actionable_open_ai_prs": 1,
        "mergeable_green": 1,
        "merge_disabled": 1,
        "needs_repair": 0,
        "pending_checks": 0,
        "review_limbo": 0,
    }
    gate = decide_auto_merge(
        merge_enabled=False,
        checks={"status": "passed", "merge_ok": True},
    )
    assert gate.action == "disabled"
    assert gate.reason == "merge_disabled"
    assert gate.waiting is True
    assert actionable_mergeable_green(remaining, merge_enabled=False) == 0
    assert soft_waiting_remaining(remaining) >= 1

    payload = _health_payload(
        cfg_mode="live",
        live=True,
        executed=True,
        progress=0,
        remaining=remaining,
        actions=[],
        planned=[],
        stuck_path=None,
        executor_enabled=True,
        merge_enabled=False,
    )
    assert payload["health"] == "waiting"
    assert payload["ok"] is True
    assert payload["idle"] is False
    assert payload["merge_enabled"] is False


def test_live_waiting_merge_disabled_legacy_remaining_without_counter():
    """Older receipts may lack merge_disabled; merge_enabled=false still waits."""
    payload = _health_payload(
        cfg_mode="live",
        live=True,
        executed=True,
        progress=0,
        remaining={
            "inbox": 0,
            "ready": 0,
            "open_ai_prs": 1,
            "mergeable_green": 2,
            "needs_repair": 0,
        },
        actions=[],
        planned=[],
        stuck_path=None,
        executor_enabled=True,
        merge_enabled=False,
    )
    assert payload["health"] == "waiting"
    assert payload["ok"] is True


def test_soft_waiting_remaining_maps_merge_policy_matrix():
    assert set(WAITING_REMAINING_FIELDS) == set(WAITING_REASONS)
    remaining = {
        "pending_checks": 1,
        "no_checks_blocked": 2,
        "merge_disabled": 3,
    }
    assert soft_waiting_remaining(remaining) == 6
    assert actionable_mergeable_green(
        {"mergeable_green": 3, "merge_disabled": 3}, merge_enabled=True
    ) == 0


def test_live_waiting_when_no_checks_blocked_only():
    payload = _health_payload(
        cfg_mode="live",
        live=True,
        executed=True,
        progress=0,
        remaining={
            "inbox": 0,
            "ready": 0,
            "open_ai_prs": 1,
            "mergeable_green": 0,
            "needs_repair": 0,
            "no_checks_blocked": 1,
            "pending_checks": 0,
        },
        actions=[],
        planned=[],
        stuck_path=None,
        executor_enabled=True,
        merge_enabled=True,
    )
    assert payload["health"] == "waiting"
    assert payload["ok"] is True


def test_progress_after_conflict_close():
    payload = _health_payload(
        cfg_mode="live",
        live=True,
        executed=True,
        progress=1,
        remaining={
            "inbox": 0,
            "ready": 1,
            "open_ai_prs": 0,
            "mergeable_green": 0,
            "needs_repair": 0,
        },
        actions=[{"step": "pr_close_conflict"}],
        planned=[],
        stuck_path=None,
        executor_enabled=True,
    )
    assert payload["health"] == "progress"
    assert payload["ok"] is True



def test_survey_errors_refuse_idle():
    payload = _health_payload(
        cfg_mode="live",
        live=False,
        executed=False,
        progress=0,
        remaining={
            "inbox": 0,
            "ready": 0,
            "open_ai_prs": 0,
            "mergeable_green": 0,
            "needs_repair": 0,
            "survey_errors": 3,
        },
        actions=[],
        planned=[],
        stuck_path=None,
        executor_enabled=True,
    )
    assert payload["idle"] is False
    assert payload["health"] == "survey_error"
    assert payload["ok"] is False
