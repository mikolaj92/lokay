from lokay.proc.classify_pr_triage_checks import classify
from lokay.proc.select_pr_triage_outcome import select


def test_green_checks_route_to_review():
    assert classify({"status": "passed", "green": True})["route"] == "review"


def test_failed_checks_route_to_repair():
    out = classify({"status": "failed"})
    assert out["route"] == "repair" and out["repairable"] is True


def test_pending_and_offline_wait():
    assert classify({"status": "pending"})["route"] == "wait"
    assert classify({"status": "offline"})["waiting"] is True


def test_none_without_require_reviews():
    assert classify({"status": "none"})["route"] == "review"


def test_none_with_require_checks_waits():
    out = classify({"status": "none", "require_checks": True})
    assert out["route"] == "wait"


def test_select_prefers_checks_repair_over_review():
    out = select({"route": "repair", "reason": "checks_failed"}, {}, {})
    assert out["route"] == "repair"


def test_select_request_changes_repairs():
    out = select(
        {"route": "review"},
        {"route": "repair", "reason": "review_requested_changes"},
        {"reason": "condition_not_met"},
    )
    assert out["route"] == "repair"


def test_select_recorded_red_local_test_repairs():
    out = select(
        {"route": "review"},
        {"route": "not_applicable"},
        {"ok": True, "passed": False, "recorded_red": True},
    )
    assert out["route"] == "repair" and out["reason"] == "test_local_failed"


def test_select_approve_green_merges():
    out = select(
        {"route": "review"},
        {"route": "not_applicable"},
        {"ok": True, "passed": True, "tested": True},
    )
    assert out["route"] == "merge"


def test_select_wait_skips_merge_and_repair():
    out = select({"route": "wait", "reason": "checks_pending"}, {}, {})
    assert out["route"] == "wait" and out["waiting"] is True
