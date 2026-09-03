"""Executor nest is one authored child. Serial launch budget stays in Fala."""

from lokay.proc import run_executor_rows


def test_executor_nest_is_one_authored_child(monkeypatch):
    calls = []

    def fake_path(*, path_id, extra_inputs, **_k):
        calls.append({"path_id": path_id, "budget": extra_inputs.get("budget")})
        return {
            "ok": True,
            "route": "idle",
            "result": {
                "route": "do",
                "launched": "started",
                "leftover": 0,
                "leftover_issues": [],
                "rows": 2,
                "spent": 2,
                "stop": "idle",
            },
        }

    monkeypatch.setattr("lokay.proc.run_executor_rows.run_path", fake_path)
    out = run_executor_rows.run(
        listed={"issues": [{"repo": "o/r", "issue": 2}, {"repo": "o/r", "issue": 3}]},
        config_path=None,
        live=True,
        pass_dir="/pass",
        budget=2,
    )
    assert len(calls) == 1
    assert calls[0]["path_id"] == "executor_rows"
    assert calls[0]["budget"] == 2
    assert out["result"]["spent"] == 2
    assert out["result"]["launched"] == "started"
    assert out["route"] == "idle"


def test_executor_nest_lifts_serial_cap(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.run_executor_rows.run_path",
        lambda **kwargs: {
            "ok": True,
            "route": "cap",
            "result": {
                "launched": "started",
                "leftover": 1,
                "leftover_issues": [{"repo": "o/r", "issue": 3}],
                "rows": 1,
                "spent": 1,
                "stop": "cap",
            },
        },
    )
    out = run_executor_rows.run(
        listed={"issues": [{"repo": "o/r", "issue": 2}, {"repo": "o/r", "issue": 3}]},
        config_path=None,
        live=True,
        pass_dir="/pass",
        budget=1,
    )
    assert out["route"] == "cap"
    assert out["result"]["spent"] == 1
    assert out["result"]["leftover"] == 1
    assert out["result"]["launched"] == "started"
