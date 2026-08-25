"""Contracts for minimal authored daemon-entry atoms."""


def test_preflight_classifier_is_closed():
    from lokay.proc.classify_daemon_preflight import classify

    assert classify({"ok": True})["route"] == "product"
    assert classify({"ok": False, "operational_overlap": True})["route"] == "overlap"
    assert classify({"ok": False, "carrier_ok": False})["route"] == "carrier_failed"
    assert classify({"ok": False, "carrier_ok": True})["route"] == "repair"


def test_restart_terminal_never_runs_stale_product():
    from lokay.proc.daemon_entry_terminal import terminal

    out = terminal(
        {"route": "repair", "preflight": {}},
        {},
        {"route": "restart", "repair": {"ok": True}},
    )["result"]
    assert out["ok"] is False and out["health"] == "self_repair_restart_required"
