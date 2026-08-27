"""Two implementable rows in one budget do not require a second daemon tick."""

from lokay.proc import run_issue_rows


def test_two_implementable_rows_one_budget_one_nest(monkeypatch):
    calls = []

    def fake_row(*, listed, last, config_path, live, pass_dir):
        calls.append({"last": dict(last or {}), "listed": listed})
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

    monkeypatch.setattr(run_issue_rows, "one_row", fake_row)
    out = run_issue_rows.run(
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

    def fake_row(*, listed, last, config_path, live, pass_dir):
        calls.append(dict(last or {}))
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

    monkeypatch.setattr(run_issue_rows, "one_row", fake_row)
    out = run_issue_rows.run(
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


def test_cap_does_not_start_a_second_tick(monkeypatch):
    def fake_row(*, listed, last, config_path, live, pass_dir):
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

    monkeypatch.setattr(run_issue_rows, "one_row", fake_row)
    out = run_issue_rows.run(
        listed={"issues": [{"repo": "o/r", "issue": 2}, {"repo": "o/r", "issue": 3}]},
        config_path=None,
        live=True,
        pass_dir="/pass",
        budget=1,
    )
    assert out["result"]["rows"] == 1
    assert out["route"] == "cap"
    assert out["result"]["leftover"] == 1
