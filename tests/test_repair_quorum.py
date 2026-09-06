"""Repeated receipts are not repeated factory attempts."""

from lokay.proc.select_repair_route import classify


def receipt(n, **fields):
    return {"kind": "pass_receipt", "ts": f"2026-09-06T00:00:{n:02d}Z",
            "health": "stall", "ok": False, "error": "factory binding missing",
            "remaining": {"ready": 1}, **fields}


def test_one_failure_keeps_factory_running():
    assert classify(receipt(1))["route"] == "factory"


def test_four_matching_failures_in_five_distinct_passes_repair():
    rows = [receipt(n) for n in range(5, 0, -1)]
    rows[2] = receipt(3, health="waiting")
    assert classify(rows[0], history=rows)["route"] == "repair"


def test_repeated_observation_is_not_five_attempts():
    row = receipt(1)
    assert classify(row, history=[row] * 5)["route"] == "factory"


def test_three_failures_and_two_waits_do_not_repair():
    rows = [receipt(n) for n in range(5, 0, -1)]
    rows[1] = receipt(4, health="waiting")
    rows[2] = receipt(3, health="repairing")
    assert classify(rows[0], history=rows)["route"] == "factory"


def test_different_failures_do_not_form_one_quorum():
    rows = [receipt(n, error=f"broken {chr(64+n)} component") for n in range(5, 0, -1)]
    assert classify(rows[0], history=rows)["route"] == "factory"


def test_both_production_bindings_read_configured_history(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from lokay.fala_organ import _handle
    from lokay.pass_history import append_pass_receipt
    from lokay.pass_receipt import write_pass_receipt

    monkeypatch.setenv("HOME", str(tmp_path))
    state = tmp_path / "state.jsonl"
    config = SimpleNamespace(state_path=state, department_self_repair=True)
    monkeypatch.setattr("lokay.proc._common.load_cfg", lambda _: config)
    monkeypatch.setattr("lokay.config.load_config", lambda _: config)
    monkeypatch.setattr("lokay.organ.departments_boundary._department_enabled", lambda *_: True)
    for n in range(1, 6):
        row = receipt(n)
        append_pass_receipt(row, state_path=state)
        write_pass_receipt(row, state_path=state)
        daemon = _handle("select_repair_route", {"config_path": "isolated.yaml"}, {})
        department = _handle("select_self_repair_department", {"config_path": "isolated.yaml"}, {})
        assert daemon["route"] == ("repair" if n == 5 else "factory")
        assert department["route"] == ("run" if n == 5 else "skip")


def test_current_delivery_overrides_old_quorum():
    rows = [receipt(n) for n in range(5, 0, -1)]
    assert classify(receipt(6, outcome="merge"), history=rows)["route"] == "factory"
