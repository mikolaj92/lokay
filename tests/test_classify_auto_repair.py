from lokay.proc.classify_auto_repair import classify


def test_moving_forward_passes_through():
    assert classify({}, {"health": "progress"})["route"] == "pass"
    assert classify({}, {"remaining": {"issue_to_pr_started": 1}})["route"] == "pass"


def test_leftover_and_preflight_host_not_repair():
    assert classify({}, {"health": "pass_ceiling"})["route"] == "pass"
    assert classify({}, {"health": "preflight_failed"})["route"] == "pass"
    assert classify({}, {"reason": "candidates_exceed_slots"})["route"] == "pass"


def test_carrier_stall_repairs_once():
    assert classify({}, {"health": "carrier_failed"})["route"] == "repair"
