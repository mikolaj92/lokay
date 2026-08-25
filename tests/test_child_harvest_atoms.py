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
