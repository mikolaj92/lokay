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
