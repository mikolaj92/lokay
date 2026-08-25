"""Contracts for minimal authored self-repair entry atoms."""


def test_entry_preconditions_are_closed():
    from lokay.proc.classify_self_repair_entry import classify

    base = {
        "carrier_ok": True,
        "issue": 7,
        "fingerprint": "x",
        "executor_enabled": True,
        "failed_names": [],
    }
    assert classify(base)["route"] == "run"
    assert classify({**base, "carrier_ok": False})["reason"] == "carrier_unhealthy"
    assert (
        classify({**base, "issue": None})["reason"]
        == "deduplicated_incident_unavailable"
    )
    assert (
        classify({**base, "failed_names": ["executor_availability"]})["reason"]
        == "bootstrap_dependency_unavailable"
    )
    assert (
        classify({**base, "executor_enabled": False})["reason"] == "executor_disabled"
    )


def test_success_requires_restart_marker():
    from lokay.proc.select_self_repair_entry_result import select

    prepared = {"issue": 7, "incident_url": "u"}
    outcome = {
        "route": "restart",
        "path": {"ok": True, "restart_required": True, "commit": "c"},
    }
    assert (
        select(prepared, {"route": "run"}, outcome, {"route": "written"})["route"]
        == "success"
    )
    assert (
        select(
            prepared,
            {"route": "run"},
            outcome,
            {"route": "terminal", "reason": "restart_marker_failed"},
        )["route"]
        == "failure"
    )
