"""Authored executor slots: Fala owns iteration, serial budget, and resume."""

from __future__ import annotations

import json
from pathlib import Path

import tomllib

from lokay.proc.classify_executor_row import classify as classify_slot
from lokay.proc.prepare_executor_rows import prepare
from lokay.proc.run_executor_row import run as run_row
from lokay.proc.select_executor_result import select as select_result
from lokay.proc.select_executor_slot import select as select_slot


def _listed(*issues: int, repo: str = "o/r") -> dict:
    rows = [{"repo": repo, "issue": n} for n in issues]
    return {"ok": True, "issues": rows, "count": len(rows)}


def _row(*, issue: int, leftover: list[dict], launched: str | None = "started", route="do"):
    return {
        "ok": True,
        "result": {
            "repo": "o/r",
            "issue": issue,
            "route": route,
            "launched": launched,
            "leftover": len(leftover),
            "leftover_issues": leftover,
        },
    }


def test_prepare_seeds_serial_budget(tmp_path: Path):
    out = prepare(
        listed=_listed(2, 3),
        last={},
        pass_dir=str(tmp_path),
        config_path=None,
        live=True,
        budget=1,
        slot_count=8,
    )
    assert out["ok"] is True
    assert out["cap"] == 1
    assert out["budget"] == 1
    assert out["spent"] == 0


def test_prepare_consumes_global_budget_for_live_detached_worker(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(
        "lokay.proc.prepare_executor_rows.live_issue_to_pr_receipts",
        lambda: [{"repo": "other/repo", "issue": 9, "pid": 123}],
    )

    out = prepare(
        listed=_listed(2, 3),
        last={},
        pass_dir=str(tmp_path),
        config_path=None,
        live=True,
        budget=1,
        slot_count=8,
    )

    assert out["cap"] == 1
    assert out["budget"] == 0
    assert out["spent"] == 1


def test_prepare_fail_closed_when_budget_exceeds_slots(tmp_path: Path):
    out = prepare(
        listed=_listed(1),
        last={},
        pass_dir=str(tmp_path),
        config_path=None,
        live=True,
        budget=9,
        slot_count=8,
    )
    assert out["ok"] is False
    assert "authored slots" in out["error"]


def test_skip_does_not_spend_launch_budget(tmp_path: Path):
    prepared = {
        "ok": True,
        "budget": 1,
        "cap": 1,
        "spent": 0,
        "pass_dir": str(tmp_path),
        "listed": _listed(2, 3),
    }
    skip = classify_slot(
        {"route": "run", "slot": 1},
        _row(issue=2, leftover=[{"repo": "o/r", "issue": 3}], launched=None, route="skip"),
        prepared=prepared,
    )
    assert skip["route"] == "continue"
    assert skip["spent"] == 0
    nxt = select_slot(prepared, skip, slot=2)
    assert nxt["route"] == "run"
    launched = classify_slot(
        nxt,
        _row(issue=3, leftover=[], launched="started"),
        prepared=prepared,
    )
    assert launched["route"] == "idle"
    assert launched["spent"] == 1
    assert launched["result"]["launched"] == "started"


def test_one_launch_caps_with_leftover(tmp_path: Path):
    prepared = {
        "ok": True,
        "budget": 1,
        "cap": 1,
        "spent": 0,
        "pass_dir": str(tmp_path),
        "listed": _listed(2, 3),
    }
    out = classify_slot(
        {"route": "run", "slot": 1},
        _row(issue=2, leftover=[{"repo": "o/r", "issue": 3}], launched="started"),
        prepared=prepared,
    )
    assert out["route"] == "cap"
    assert out["spent"] == 1
    assert out["leftover"] == 1
    assert select_slot(prepared, out, slot=2)["route"] == "empty"
    cursor = json.loads((tmp_path / "executor-rows.json").read_text(encoding="utf-8"))
    assert cursor["spent"] == 1
    assert cursor["last"]["leftover"] == 1


def test_two_launches_inside_budget(tmp_path: Path):
    prepared = {
        "ok": True,
        "budget": 2,
        "cap": 2,
        "spent": 0,
        "pass_dir": str(tmp_path),
        "listed": _listed(2, 3),
    }
    first = classify_slot(
        {"route": "run", "slot": 1},
        _row(issue=2, leftover=[{"repo": "o/r", "issue": 3}], launched="started"),
        prepared=prepared,
    )
    assert first["route"] == "continue"
    second = classify_slot(
        {"route": "run", "slot": 2},
        _row(issue=3, leftover=[], launched="started"),
        prepared={**prepared, "spent": first["spent"]},
    )
    assert second["route"] == "idle"
    assert second["spent"] == 2


def test_select_result_reports_started_and_serial_cap():
    out = select_result(
        {"cap": 1, "budget": 1},
        [
            {
                "route": "cap",
                "spent": 1,
                "leftover": 1,
                "leftover_issues": [{"repo": "o/r", "issue": 3}],
                "result": {"launched": "started", "issue": 2},
            }
        ],
    )
    assert out["route"] == "cap"
    assert out["department"] == "executor"
    assert out["result"]["launched"] == "started"
    assert out["result"]["spent"] == 1


def test_run_executor_row_is_one_child_path(monkeypatch):
    calls = []

    def fake_run_path(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "result": {"route": "do", "launched": "started"}}

    monkeypatch.setattr("lokay.proc.run_executor_row.run_path", fake_run_path)
    out = run_row(
        listed=_listed(2),
        last={},
        pass_dir="/pass",
        config_path=None,
        live=True,
        slot=1,
    )
    assert len(calls) == 1
    assert calls[0]["path_id"] == "executor_row"
    assert out["result"]["launched"] == "started"


def test_package_owns_authored_executor_slots():
    package = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "fala/lokay.fala-package.toml").read_text(
            encoding="utf-8"
        )
    )
    path = next(row for row in package["correlation_paths"] if row["id"] == "executor_rows")
    ids = [str(node["id"]) for node in path["effectors"]]
    assert ids[0] == "prepare_executor_rows"
    assert ids[-1] == "select_executor_result"
    assert [f"select_executor_slot_{n}" for n in range(1, 9)] == [
        node for node in ids if node.startswith("select_executor_slot_")
    ]
    by_id = {node["id"]: node for node in path["effectors"]}
    assert by_id["run_executor_row_1"]["when"] == {
        "upstream": "select_executor_slot_1",
        "path": "route",
        "equals": "run",
    }
    assert "run_executor_rows" not in ids


def test_run_executor_rows_nests_once_and_has_no_python_loop():
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "lokay"
        / "proc"
        / "run_executor_rows.py"
    ).read_text(encoding="utf-8")
    assert "while True" not in src
    assert 'path_id="executor_rows"' in src
    assert 'path_id="executor_row"' not in src
