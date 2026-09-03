from lokay.proc.run_issue_sieve_rows import run


def _listed(count: int) -> dict:
    issues = [{"repo": "o/r", "issue": n} for n in range(1, count + 1)]
    return {"ok": True, "issues": issues, "count": count, "overflow": False}


def test_sieve_nest_is_one_authored_child(monkeypatch):
    calls = []

    def fake_run_path(**kwargs):
        calls.append(kwargs)
        return {
            "ok": True,
            "route": "cap",
            "result": {
                "route": "do",
                "leftover": 7,
                "leftover_issues": [{"repo": "o/r", "issue": n} for n in range(6, 13)],
                "rows": 5,
                "spent": 5,
                "stop": "cap",
            },
        }

    monkeypatch.setattr("lokay.proc.run_issue_sieve_rows.run_path", fake_run_path)
    out = run(
        listed=_listed(12),
        config_path=None,
        live=True,
        pass_dir="/pass",
        budget=5,
        last={},
    )
    assert len(calls) == 1
    assert calls[0]["path_id"] == "issue_sieve_rows"
    assert calls[0]["extra_inputs"]["budget"] == 5
    assert out["route"] == "cap"
    assert out["result"]["leftover"] == 7
    assert out["launched"] is None


def test_sieve_nest_lifts_idle_receipt(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.run_issue_sieve_rows.run_path",
        lambda **kwargs: {
            "ok": True,
            "route": "idle",
            "result": {"leftover": 0, "leftover_issues": [], "rows": 2, "stop": "idle"},
        },
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
    assert out["result"]["leftover"] == 0
    assert out["result"]["leftover_issues"] == []
