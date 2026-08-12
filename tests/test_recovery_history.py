import json

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
        row = observe_run(
            state_path=state,
            state_offset=0,
            mill={"ok": False, "health": health, "error": f"mill {health}", "progress": 0},
        )
        assert row["fingerprint"] is None
        assert row["health"] == health
