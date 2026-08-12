"""Health rules: no green noop while work remains."""

from lokay.compose.tick import _health_payload


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
