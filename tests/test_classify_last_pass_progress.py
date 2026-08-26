"""Last-pass repair gate: new PR or merge only; leftover/empty/stale stay factory."""

from lokay.fala_organ import _handle as fala_handle
from lokay.pass_receipt import build_pass_receipt
from lokay.proc.classify_last_pass_progress import classify, leftover_skip_signal


def _receipt(**fields):
    base = {
        "kind": "pass_receipt",
        "ts": "2026-08-26T00:00:00Z",
        "ok": False,
        "health": "stall",
        "idle": False,
        "progress": 0,
        "remaining": {"inbox": 1, "ready": 1, "open_ai_prs": 0},
    }
    base.update(fields)
    return base


def test_new_pr_is_moved_forward():
    out = classify(_receipt(new_pr=True, health="progress", ok=True))
    assert out["route"] == "factory" and out["reason"] == "moved_forward"
    assert out["moved_forward"] is True


def test_merge_is_moved_forward():
    out = classify(_receipt(merged=True, health="progress", ok=True))
    assert out["route"] == "factory" and out["moved_forward"] is True


def test_leftover_overflow_skip_does_not_start_repair():
    receipt = _receipt(
        leftover_skip=True,
        reason="leftover_overflow",
        health="stall",
        error="leftover closeout catalog exceeds authored slots",
    )
    assert leftover_skip_signal(receipt) is True
    out = classify(receipt)
    assert out["route"] == "factory" and out["reason"] == "leftover_skip"


def test_leftover_overflow_error_text_does_not_start_repair():
    out = classify(
        _receipt(error="leftover closeout catalog exceeds authored slots: 200>30")
    )
    assert out["route"] == "factory" and out["reason"] == "leftover_skip"


def test_empty_survey_does_not_start_repair():
    out = classify(
        _receipt(
            health="idle",
            idle=True,
            ok=True,
            remaining={
                "inbox": 0,
                "ready": 0,
                "open_ai_prs": 0,
                "issue_to_pr_started": 0,
                "survey_errors": 0,
            },
        )
    )
    assert out["route"] == "factory" and out["reason"] == "empty_survey"


def test_stale_or_missing_receipt_does_not_start_repair():
    assert classify(None)["reason"] == "stale_receipt"
    assert classify({})["reason"] == "stale_receipt"
    assert classify({"health": "stall"})["reason"] == "stale_receipt"


def test_waiting_receipt_does_not_start_repair():
    out = classify(_receipt(health="waiting", ok=True))
    assert out["route"] == "factory" and out["reason"] == "waiting"


def test_occupied_inflight_does_not_start_repair():
    out = classify(
        _receipt(
            health="stall",
            remaining={"inbox": 0, "ready": 0, "issue_to_pr_started": 1},
        )
    )
    assert out["route"] == "factory" and out["reason"] == "occupied"


def test_did_not_move_starts_repair():
    out = classify(_receipt(health="stall", ok=False, error="no product delivery"))
    assert out == {
        "ok": True,
        "route": "repair",
        "reason": "did_not_move",
        "moved_forward": False,
        "fingerprint": "did_not_move",
        "evidence": "no product delivery",
    }


def test_receipt_persists_leftover_skip_and_delivery_flags():
    receipt = build_pass_receipt(
        tick={
            "ok": True,
            "health": "progress",
            "leftover_skip": True,
            "reason": "leftover_overflow",
            "merged_this_pass": ["mikolaj92/lokay"],
            "actions": [{"step": "pr_create", "pr": 9}],
            "remaining": {},
        },
        merge_enabled=True,
        max_issue_to_pr_per_pass=1,
    )
    assert receipt["leftover_skip"] is True
    assert receipt["new_pr"] is True
    assert receipt["merged"] is True


def test_organ_skips_repair_for_leftover_overflow(monkeypatch):
    repair_calls: list[object] = []

    def forbid(*_a, **_k):
        repair_calls.append(True)
        raise AssertionError("recovery_run_self_repair must not run for leftover skip")

    monkeypatch.setattr("lokay.proc.recovery_run_self_repair.main", forbid)
    monkeypatch.setattr("lokay.proc.recovery_incident.main", forbid)
    classified = classify(
        _receipt(leftover_skip=True, reason="leftover_overflow", health="stall")
    )
    incident = fala_handle(
        "recovery_incident",
        {},
        {"classify_last_pass_progress": classified},
    )
    repair = fala_handle(
        "recovery_run_self_repair",
        {"config_path": "unused.yaml"},
        {
            "classify_last_pass_progress": classified,
            "recovery_incident": incident,
        },
    )
    assert incident["skipped"] is True
    assert repair["skipped"] is True
    assert repair["reason"] == "leftover_skip"
    assert repair_calls == []
