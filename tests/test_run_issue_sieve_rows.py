from lokay.proc.run_issue_sieve_rows import run


def _listed(count: int) -> dict:
    issues = [{"repo": "o/r", "issue": n} for n in range(1, count + 1)]
    return {"ok": True, "issues": issues, "count": count, "overflow": False}


def _row_for(inputs: dict) -> dict:
    listed = list(inputs["listed"]["issues"])
    last = inputs.get("last") or {}
    leftover = list(last.get("leftover_issues") or listed)
    picked = leftover[0]
    remaining = leftover[1:]
    return {
        "ok": True,
        "result": {
            **picked,
            "route": "do",
            "launched": None,
            "leftover": len(remaining),
            "leftover_issues": remaining,
        },
    }


def test_large_sieve_stops_at_budget_and_preserves_leftover(monkeypatch):
    calls = []

    def fake_run_path(**kwargs):
        calls.append(kwargs)
        return _row_for(kwargs["extra_inputs"])

    monkeypatch.setattr("lokay.proc.run_issue_sieve_rows.run_path", fake_run_path)
    out = run(
        listed=_listed(12),
        config_path=None,
        live=True,
        pass_dir="/pass",
        budget=5,
        last={},
    )

    assert out["route"] == "cap"
    assert out["result"]["stop"] == "cap"
    assert out["result"]["rows"] == 5
    assert out["result"]["spent"] == 5
    assert out["result"]["budget"] == 5
    assert out["result"]["leftover"] == 7
    assert [row["issue"] for row in out["result"]["leftover_issues"]] == list(
        range(6, 13)
    )
    assert len(calls) == 5


def test_small_sieve_reaches_idle_before_budget(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.run_issue_sieve_rows.run_path",
        lambda **kwargs: _row_for(kwargs["extra_inputs"]),
    )
    out = run(
        listed=_listed(2),
        config_path=None,
        live=True,
        pass_dir="/pass",
        budget=5,
        last={},
    )
    assert out["route"] == "idle"
    assert out["result"]["rows"] == 2
    assert out["result"]["leftover"] == 0
    assert out["result"]["leftover_issues"] == []
