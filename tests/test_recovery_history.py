import json

from lokay.fala_organ import _handle as fala_handle
from lokay.recovery_history import (
    history_path_for,
    normalize_failure,
    observe_run,
    record_observation,
)


def test_normalization_removes_run_specific_numbers():
    assert normalize_failure("push failed pid 123 sha deadbeef") == normalize_failure(
        "push failed pid 999 sha cafebabe"
    )


def test_quorum_requires_four_matching_failures_in_five(tmp_path):
    path = tmp_path / "history.json"
    signal = None
    for fingerprint in ["same", "same", "other", "same", "same"]:
        signal = record_observation(
            path,
            {
                "fingerprint": fingerprint,
                "evidence": fingerprint,
                "delivered": False,
                "health": "stall",
                "progress": 0,
            },
        )
    assert signal == {
        "fingerprint": "same",
        "matches": 4,
        "window": 5,
        "evidence": "same",
        "health": "confirmed_stall",
    }


def test_successful_delivery_breaks_systemic_failure_evidence(tmp_path):
    state = tmp_path / "state.jsonl"
    state.write_text(
        json.dumps(
            {
                "kind": "issue_to_pr",
                "ok": True,
                "terminal": {"pr_create": {"pr": {"url": "https://example.test/pr/1"}}},
            }
        )
        + "\n"
        + json.dumps({"kind": "other", "ok": False, "error": "same failure"})
        + "\n"
    )
    row = observe_run(state_path=state, state_offset=0, mill={"ok": False, "health": "budget_exhausted", "progress": 9})
    assert row["delivered"] is True
    assert row["fingerprint"] is None


def test_skipped_pr_merge_is_not_delivery(tmp_path):
    state = tmp_path / "state.jsonl"
    state.write_text(
        json.dumps(
            {
                "kind": "pr_triage",
                "ok": True,
                "skipped": True,
                "reason": "llm_review_requested_changes",
                "terminal": {
                    "pr_merge": {"ok": True, "skipped": True, "reason": "llm_review_not_approved"}
                },
            }
        )
        + "\n"
    )
    row = observe_run(
        state_path=state,
        state_offset=0,
        mill={"ok": False, "health": "budget_exhausted", "progress": 8},
    )
    assert row["delivered"] is False
    assert row["fingerprint"] is not None
    assert row["evidence"] == "budget_exhausted"


def test_actual_pr_merge_is_delivery(tmp_path):
    state = tmp_path / "state.jsonl"
    state.write_text(
        json.dumps(
            {
                "kind": "pr_triage",
                "ok": True,
                "terminal": {"pr_merge": {"ok": True, "merged": True}},
            }
        )
        + "\n"
    )
    row = observe_run(
        state_path=state,
        state_offset=0,
        mill={"ok": False, "health": "budget_exhausted", "progress": 8},
    )
    assert row["delivered"] is True
    assert row["fingerprint"] is None


def test_observation_reads_only_current_run_tail(tmp_path):
    state = tmp_path / "state.jsonl"
    state.write_text(json.dumps({"ok": False, "error": "old failure"}) + "\n")
    offset = state.stat().st_size
    with state.open("a") as handle:
        handle.write(json.dumps({"ok": False, "error": "new failure 123"}) + "\n")
    row = observe_run(state_path=state, state_offset=offset, mill={"ok": False})
    assert "new failure" in row["evidence"]
    assert "old failure" not in row["evidence"]
    assert history_path_for(state) == tmp_path / "recovery-history.json"


def test_waiting_or_repairing_mill_envelope_is_not_failure_fingerprint(tmp_path):
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    for health in ("waiting", "repairing"):
        # Both ok=false (defensive) and ok=true (mill early-exit / #55 receipt shape).
        for ok_flag in (False, True):
            row = observe_run(
                state_path=state,
                state_offset=0,
                mill={
                    "ok": ok_flag,
                    "health": health,
                    "error": f"mill {health}",
                    "progress": 0,
                },
            )
            assert row["fingerprint"] is None
            assert row["health"] == health


def test_pending_ci_and_needs_review_triage_events_do_not_fingerprint(tmp_path):
    """Review limbo / pending CI / parked needs-review are soft product waits."""
    state = tmp_path / "state.jsonl"
    state.write_text(
        "\n".join(
            json.dumps(row)
            for row in (
                {
                    "kind": "pr_triage",
                    "ok": True,
                    "skipped": True,
                    "waiting": True,
                    "reason": "checks_pending",
                },
                {
                    "kind": "pr_triage",
                    "ok": True,
                    "skipped": True,
                    "reason": "llm_review_escalated_needs_review",
                    "needs_review": True,
                    "escalated": True,
                },
                {
                    "kind": "pr_repair",
                    "ok": False,
                    "error": "repair while waiting on CI",
                },
            )
        )
        + "\n",
        encoding="utf-8",
    )
    row = observe_run(
        state_path=state,
        state_offset=0,
        mill={"ok": True, "health": "waiting", "progress": 0},
    )
    assert row["fingerprint"] is None
    assert row["health"] == "waiting"


def test_event_failures_under_waiting_or_repairing_do_not_fingerprint(tmp_path):
    """Per-event pr_repair/issue_to_pr failures during soft wait must not escalate."""
    state = tmp_path / "state.jsonl"
    state.write_text(
        json.dumps(
            {
                "kind": "pr_repair",
                "ok": False,
                "error": "repair agent failed: push rejected",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    for health in ("waiting", "repairing", "idle", "progress"):
        row = observe_run(
            state_path=state,
            state_offset=0,
            mill={"ok": True, "health": health, "progress": 0},
        )
        assert row["fingerprint"] is None, health
        assert row["evidence"] == ""


def test_soft_waiting_rows_cannot_fill_quorum(tmp_path):
    path = tmp_path / "history.json"
    # Four soft rows with a stamped fingerprint must not confirm stall.
    for _ in range(4):
        signal = record_observation(
            path,
            {
                "fingerprint": "soft-fp",
                "evidence": "should not count",
                "delivered": False,
                "health": "waiting",
                "progress": 0,
            },
        )
        assert signal is None
    # Mix soft waits into a window so hard failures cannot reach 4-of-5.
    for health in ("stall", "waiting", "stall", "repairing", "stall"):
        signal = record_observation(
            path,
            {
                "fingerprint": "hard-fp",
                "evidence": "hard",
                "delivered": False,
                "health": health,
                "progress": 0,
            },
        )
    assert signal is None
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert all(
        row.get("fingerprint") is None
        for row in stored
        if row.get("health") in {"waiting", "repairing"}
    )


def test_waiting_repairing_mill_never_escalates_to_self_repair(monkeypatch, tmp_path):
    """Mill envelopes with soft health must skip recovery_run_self_repair."""
    state = tmp_path / "state.jsonl"
    state.write_text(
        json.dumps({"kind": "pr_repair", "ok": False, "error": "same repair fail"})
        + "\n",
        encoding="utf-8",
    )
    repair_calls: list[object] = []

    def forbid_repair(*_a, **_k):
        repair_calls.append(True)
        raise AssertionError("recovery_run_self_repair must not run for soft mill health")

    monkeypatch.setattr(
        "lokay.proc.recovery_run_self_repair.main",
        forbid_repair,
    )
    monkeypatch.setattr(
        "lokay.proc.recovery_incident.main",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("recovery_incident must not run without quorum")
        ),
    )

    for health in ("waiting", "repairing"):
        # Drain any prior soft history between scenarios.
        history = history_path_for(state)
        if history.exists():
            history.unlink()
        for _ in range(5):
            observation = observe_run(
                state_path=state,
                state_offset=0,
                mill={"ok": True, "health": health, "progress": 0},
            )
            assert observation["fingerprint"] is None
            recorded = fala_handle(
                "recovery_record",
                {},
                {
                    "recovery_begin": {"state_path": str(state)},
                    "recovery_observe": {"observation": observation},
                },
            )
            assert recorded["ok"] is True
            assert recorded["confirmed"] is not True
            incident = fala_handle(
                "recovery_incident",
                {},
                {"recovery_record": recorded},
            )
            assert incident.get("skipped") is True
            assert incident.get("reason") == "stall_quorum_not_met"
            repair = fala_handle(
                "recovery_run_self_repair",
                {"config_path": str(tmp_path / "unused.yaml")},
                {"recovery_incident": incident},
            )
            assert repair.get("skipped") is True
            assert repair_calls == []
