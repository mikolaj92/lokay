"""Contracts for minimal detached-child harvest reducers."""


def _facts(stuck, events=None, history=None):
    return {
        "stuck": stuck,
        "events": events or {},
        "history": history or {},
        "repos": ["owner/repo"],
        "closed_catalog": {},
        "cycle_dir": "/missing",
        "home": "/missing",
        "stuck_path": "/tmp/s",
    }


def test_delivery_stage_clears_only_stale_no_pr():
    from lokay.proc.reconcile_harvest_deliveries import reconcile

    stuck = {
        "issues": {
            "owner/repo#7": {"blocked": True, "reason": "no_pr"},
            "owner/repo#8": {"blocked": True, "reason": "test_local_failed"},
        }
    }
    out = reconcile(
        _facts(stuck, {"owner/repo#7": {"ok": True}, "owner/repo#8": {"ok": True}})
    )
    assert (
        "owner/repo#7" not in out["stuck"]["issues"]
        and "owner/repo#8" in out["stuck"]["issues"]
    )


def test_closed_catalog_stage_uses_collected_facts_only():
    from lokay.proc.clear_harvest_closed_rows import clear

    facts = _facts(
        {
            "issues": {
                "owner/repo#7": {"blocked": True},
                "owner/repo#8": {"blocked": True},
            }
        }
    )
    facts["closed_catalog"] = {"owner/repo": [7]}
    out = clear(facts)
    assert set(out["stuck"]["issues"]) == {"owner/repo#8"}


def test_harvest_factory_wrapper_contains_no_routing():
    import inspect

    from lokay.proc.harvest_factory_children import harvest

    source = inspect.getsource(harvest)
    assert "if " not in source and "for " not in source


def test_reaped_fail_closed_skips_record_failure(tmp_path):
    """lokay#1084: reconcile must not renew cooldown from a reaped receipt."""
    import json
    from pathlib import Path

    from lokay.proc.reconcile_dead_child_receipts import reconcile

    cycle = tmp_path / "cycle"
    cycle.mkdir()
    receipt_path = cycle / "owner__repo-9.json"
    row = {
        "ok": False,
        "reaped": True,
        "reason": "no_pr",
        "pid": 12345,
        "repo": "owner/repo",
        "issue": 9,
    }
    receipt_path.write_text(json.dumps(row), encoding="utf-8")
    row = dict(row)
    row["_path"] = str(receipt_path)
    facts = _facts(
        {"issues": {}},
        events={"owner/repo#9": {"ok": True, "delivered": False, "reason": "no_delivery"}},
    )
    facts["receipts"] = [row]
    facts["cycle_dir"] = str(cycle)
    facts["home"] = str(tmp_path)
    out = reconcile(facts)
    assert "owner/repo#9" not in out["stuck"]["issues"]
    # Receipt left untouched (still reaped, no rewrite required).
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["reaped"] is True


def test_fresh_fail_closed_receipt_records_cooldown_once(tmp_path):
    """First harvest of a dead FAIL_CLOSED receipt still applies cooldown."""
    import json

    from lokay.proc.reconcile_dead_child_receipts import reconcile

    cycle = tmp_path / "cycle"
    cycle.mkdir()
    receipt_path = cycle / "owner__repo-9.json"
    row = {
        "ok": True,
        "detached": True,
        "pid": 12345,
        "repo": "owner/repo",
        "issue": 9,
    }
    receipt_path.write_text(json.dumps(row), encoding="utf-8")
    row = dict(row)
    row["_path"] = str(receipt_path)
    facts = _facts(
        {"issues": {}},
        events={
            "owner/repo#9": {
                "ok": False,
                "reason": "test_local_failed",
                "error": "boom",
            }
        },
    )
    facts["receipts"] = [row]
    facts["cycle_dir"] = str(cycle)
    facts["home"] = str(tmp_path)
    out = reconcile(facts)
    issue_row = out["stuck"]["issues"]["owner/repo#9"]
    assert issue_row.get("blocked") is True
    assert issue_row.get("reason") == "test_local_failed"
    assert issue_row.get("cooldown_until")
    stamped = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert stamped.get("reaped") is True

