from lokay.compose.daemon_cycle import finalize_daemon_payload


def test_finalize_daemon_payload_drops_bulky_orchestration_details():
    payload = {
        "ok": True,
        "health": "idle",
        "remaining": {"ready": 2},
        "progress": 1,
        "terminal": {
            "recovery_factory": "m" * 90_000,
            "recovery_observe": "o" * 90_000,
        },
        "steps": {"factory_pass": "s" * 185_000},
        "last": {
            "steps": {"factory_pass": "nested"},
            "terminal": {"recovery_factory": "nested"},
            "fala": {"host": "nested"},
        },
        "fala": {"host": "f" * 90_000},
    }

    out = finalize_daemon_payload(payload)

    assert out == {
        "ok": True,
        "health": "idle",
        "remaining": {"ready": 2},
        "progress": 1,
    }
    assert "terminal" in payload
    assert "steps" in payload
    assert "last" in payload
