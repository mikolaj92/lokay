"""Two implementable rows in one budget do not require a second daemon tick."""

from lokay.proc import run_executor_rows


def test_two_implementable_rows_one_budget_one_nest(monkeypatch):
    calls = []

    def fake_path(*, path_id, extra_inputs, **_k):
        assert path_id == "executor_row"
        last = extra_inputs.get("last") or {}
        calls.append({"last": dict(last), "listed": extra_inputs.get("listed")})
        if not last:
            return {
                "ok": True,
                "result": {
                    "route": "do",
                    "repo": "o/r",
                    "issue": 2,
                    "launched": "started",
                    "leftover": 1,
                    "leftover_issues": [{"repo": "o/r", "issue": 3}],
                },
            }
        return {
            "ok": True,
            "result": {
                "route": "do",
                "repo": "o/r",
                "issue": 3,
                "launched": "started",
                "leftover": 0,
                "leftover_issues": [],
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
    assert len(calls) == 2
    assert calls[1]["last"]["issue"] == 2
    assert out["result"]["rows"] == 2
    assert out["result"]["spent"] == 2
    assert out["result"]["launched"] == "started"
    assert out["result"]["leftover"] == 0
    assert out["route"] == "idle"


def test_skip_then_next_row_same_budget(monkeypatch):
    calls = []

    def fake_path(*, path_id, extra_inputs, **_k):
        assert path_id == "executor_row"
        last = extra_inputs.get("last") or {}
        calls.append(dict(last))
        if not last:
            return {
                "ok": True,
                "result": {
                    "route": "skip",
                    "repo": "o/r",
                    "issue": 2,
                    "leftover": 1,
                    "leftover_issues": [{"repo": "o/r", "issue": 3}],
                },
            }
        return {
            "ok": True,
            "result": {
                "route": "do",
                "repo": "o/r",
                "issue": 3,
                "launched": "started",
                "leftover": 0,
                "leftover_issues": [],
            },
        }

    monkeypatch.setattr("lokay.proc.run_executor_rows.run_path", fake_path)
    out = run_executor_rows.run(
        listed={"issues": [{"repo": "o/r", "issue": 2}, {"repo": "o/r", "issue": 3}]},
        config_path=None,
        live=True,
        pass_dir="/pass",
        budget=1,
    )
    assert len(calls) == 2
    assert out["result"]["spent"] == 1
    assert out["result"]["launched"] == "started"
    assert out["route"] == "idle"


def test_coding_not_implemented_row_does_not_abort_catalog(monkeypatch):
    """A row whose coding is not implemented still finishes; the loop continues."""
    from lokay.proc.classify_issue_to_pr_subflow import classify

    calls = []

    def fake_path(*, path_id, extra_inputs, **_k):
        assert path_id == "executor_row"
        last = extra_inputs.get("last") or {}
        calls.append(dict(last))
        if not last:
            child = classify(error=RuntimeError("condition_source_not_succeeded"))
            return {
                "ok": True,
                "result": {
                    **child,
                    "route": child["route"],
                    "leftover": 1,
                    "leftover_issues": [{"repo": "o/r", "issue": 3}],
                },
            }
        return {
            "ok": True,
            "result": {
                "route": "do",
                "repo": "o/r",
                "issue": 3,
                "launched": "started",
                "leftover": 0,
                "leftover_issues": [],
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
    assert len(calls) == 2
    assert calls[0] == {}
    assert out["result"]["rows"] == 2
    assert out["result"]["launched"] == "started"
    assert out["route"] == "idle"


def test_cap_does_not_start_a_second_tick(monkeypatch):
    def fake_path(*, path_id, extra_inputs, **_k):
        assert path_id == "executor_row"
        return {
            "ok": True,
            "result": {
                "route": "do",
                "repo": "o/r",
                "issue": 2,
                "launched": "started",
                "leftover": 1,
                "leftover_issues": [{"repo": "o/r", "issue": 3}],
            },
        }

    monkeypatch.setattr("lokay.proc.run_executor_rows.run_path", fake_path)
    out = run_executor_rows.run(
        listed={"issues": [{"repo": "o/r", "issue": 2}, {"repo": "o/r", "issue": 3}]},
        config_path=None,
        live=True,
        pass_dir="/pass",
        budget=1,
    )
    assert out["result"]["rows"] == 1
    assert out["route"] == "cap"
    assert out["result"]["leftover"] == 1
