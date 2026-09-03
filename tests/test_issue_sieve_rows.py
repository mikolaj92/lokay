"""Authored issue-sieve slots: Fala owns iteration, budget, and resume."""

from __future__ import annotations

import json
from pathlib import Path

import tomllib

from lokay.proc.classify_issue_sieve_row import classify as classify_slot
from lokay.proc.prepare_issue_sieve import prepare
from lokay.proc.run_issue_sieve_row import run as run_row
from lokay.proc.select_issue_sieve_result import select as select_result
from lokay.proc.select_issue_sieve_slot import select as select_slot


def _listed(count: int) -> dict:
    issues = [{"repo": "o/r", "issue": n} for n in range(1, count + 1)]
    return {"ok": True, "issues": issues, "count": count, "overflow": False}


def _row_for(last: dict, listed: dict) -> dict:
    leftover = list(last.get("leftover_issues") or listed["issues"])
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


def test_prepare_seeds_budget_and_empty_cursor(tmp_path: Path):
    out = prepare(
        listed=_listed(3),
        last={},
        pass_dir=str(tmp_path),
        config_path=None,
        live=True,
        budget=5,
        slot_count=5,
    )
    assert out["ok"] is True
    assert out["route"] == "run"
    assert out["budget"] == 5
    assert out["last"] == {}
    assert out["slot_count"] == 5


def test_prepare_fail_closed_when_budget_exceeds_slots(tmp_path: Path):
    out = prepare(
        listed=_listed(1),
        last={},
        pass_dir=str(tmp_path),
        config_path=None,
        live=True,
        budget=9,
        slot_count=5,
    )
    assert out["ok"] is False
    assert "authored slots" in out["error"]


def test_prepare_resumes_cursor_without_rescanning(tmp_path: Path):
    cursor = {
        "last": {
            "leftover": 7,
            "leftover_issues": [{"repo": "o/r", "issue": n} for n in range(6, 13)],
            "route": "do",
        },
        "spent": 5,
    }
    (tmp_path / "issue-sieve.json").write_text(json.dumps(cursor), encoding="utf-8")
    out = prepare(
        listed=_listed(12),
        last={},
        pass_dir=str(tmp_path),
        config_path=None,
        live=True,
        budget=5,
        slot_count=5,
    )
    assert [row["issue"] for row in out["last"]["leftover_issues"]] == list(range(6, 13))
    assert out["spent"] == 5


def test_slot_one_always_runs_even_on_zero_budget():
    prepared = {"ok": True, "budget": 0}
    assert select_slot(prepared, {}, slot=1)["route"] == "run"
    assert select_slot(prepared, {"route": "continue"}, slot=2)["route"] == "empty"


def test_later_slot_runs_only_after_continue_inside_budget():
    prepared = {"ok": True, "budget": 5}
    assert select_slot(prepared, {"route": "continue"}, slot=2)["route"] == "run"
    assert select_slot(prepared, {"route": "idle"}, slot=2)["route"] == "empty"
    assert select_slot(prepared, {"route": "cap"}, slot=2)["route"] == "empty"
    assert select_slot(prepared, {"route": "continue"}, slot=6)["route"] == "empty"


def test_classify_persists_cursor_and_caps_at_budget(tmp_path: Path):
    listed = _listed(12)
    last: dict = {}
    selected = {"route": "run", "slot": 5}
    row = _row_for(
        {
            "leftover_issues": [{"repo": "o/r", "issue": n} for n in range(5, 13)],
        },
        listed,
    )
    out = classify_slot(
        selected,
        row,
        prepared={"budget": 5, "pass_dir": str(tmp_path), "listed": listed},
    )
    assert out["route"] == "cap"
    assert out["leftover"] == 7
    cursor = json.loads((tmp_path / "issue-sieve.json").read_text(encoding="utf-8"))
    assert cursor["spent"] == 5
    assert [row["issue"] for row in cursor["last"]["leftover_issues"]] == list(
        range(6, 13)
    )


def test_classify_empty_slot_does_not_count_as_a_row(tmp_path: Path):
    out = classify_slot(
        {"route": "empty", "slot": 3},
        {},
        prepared={"budget": 5, "pass_dir": str(tmp_path), "listed": _listed(2)},
    )
    assert out["route"] == "empty"
    assert not (tmp_path / "issue-sieve.json").exists()


def test_select_result_prefers_idle_then_cap():
    rows = [
        {"route": "continue", "result": {"leftover": 2}},
        {"route": "idle", "result": {"leftover": 0, "leftover_issues": []}},
        {"route": "empty"},
    ]
    out = select_result({"budget": 5}, rows)
    assert out["route"] == "idle"
    assert out["result"]["leftover"] == 0
    assert out["department"] == "issue_triage"
    assert out["launched"] is None


def test_run_issue_sieve_row_is_one_child_path(monkeypatch):
    calls = []

    def fake_run_path(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "result": {"route": "do", "leftover": 1}}

    monkeypatch.setattr("lokay.proc.run_issue_sieve_row.run_path", fake_run_path)
    out = run_row(
        listed=_listed(2),
        last={},
        pass_dir="/pass",
        config_path=None,
        live=True,
        slot=1,
    )
    assert len(calls) == 1
    assert calls[0]["path_id"] == "issue_sieve_row"
    assert calls[0]["extra_inputs"]["last"] == {}
    assert out["result"]["route"] == "do"


def test_package_owns_authored_sieve_slots():
    package = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "fala/lokay.fala-package.toml").read_text(
            encoding="utf-8"
        )
    )
    path = next(row for row in package["correlation_paths"] if row["id"] == "issue_sieve_rows")
    ids = [str(node["id"]) for node in path["effectors"]]
    assert ids[0] == "prepare_issue_sieve"
    assert ids[-1] == "select_issue_sieve_result"
    assert [f"select_issue_sieve_slot_{n}" for n in range(1, 6)] == [
        node for node in ids if node.startswith("select_issue_sieve_slot_")
    ]
    assert [f"run_issue_sieve_row_{n}" for n in range(1, 6)] == [
        node for node in ids if node.startswith("run_issue_sieve_row_")
    ]
    by_id = {node["id"]: node for node in path["effectors"]}
    assert by_id["run_issue_sieve_row_1"]["when"] == {
        "upstream": "select_issue_sieve_slot_1",
        "path": "route",
        "equals": "run",
    }
    assert "run_issue_sieve_rows" not in ids


def test_run_issue_sieve_rows_nests_once_and_has_no_python_loop():
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "lokay"
        / "proc"
        / "run_issue_sieve_rows.py"
    ).read_text(encoding="utf-8")
    assert "while True" not in src
    assert 'path_id="issue_sieve_rows"' in src
    assert 'path_id="issue_sieve_row"' not in src
