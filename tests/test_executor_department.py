"""executor department: a do issue becomes an open PR. Off = zero ai/fix."""

import tomllib
from pathlib import Path

from lokay.proc.select_executor_department import select as select_dept
from lokay.proc.select_issue_do_row import pick, select
from lokay.proc.select_issue_executor import select as select_launch
from lokay.proc.summarize_executor_department import summarize


def _path(path_id: str) -> dict:
    package = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "fala/lokay.fala-package.toml").read_text(
            encoding="utf-8"
        )
    )
    return next(row for row in package["correlation_paths"] if row["id"] == path_id)


def test_pick_ready_labels_becomes_do_without_triage() -> None:
    listed = {
        "issues": [
            {
                "repo": "o/r",
                "issue": 9,
                "labels": ["ai:ready"],
            }
        ],
        "count": 1,
        "overflow": False,
    }
    picked = pick(listed, {})
    assert picked["route"] == "ready"
    out = select(picked, listed)
    assert out["route"] == "do"
    assert out["issue"] == 9


def test_ready_row_becomes_do_without_triage() -> None:
    picked = {
        "route": "issue",
        "repo": "o/r",
        "issue": 9,
        "labels": ["ai:ready"],
    }
    out = select(picked, {"issues": [picked]})
    assert out["route"] == "do"
    assert out["issue"] == 9


def test_foreign_assignee_is_not_takeable_at_pick() -> None:
    listed = {
        "issues": [
            {
                "repo": "o/r",
                "issue": 1,
                "assignees": ["someone-else"],
                "labels": ["ai:ready"],
            }
        ]
    }
    picked = pick(listed, {})
    assert picked.get("route") == "none"
    assert picked.get("reason") == "foreign_assignee"


def test_disabled_executor_does_not_launch() -> None:
    assert select_dept(enabled=False)["reason"] == "executor_disabled"
    assert select_launch({"route": "do", "repo": "o/r", "issue": 1}, enabled=False) == {
        "ok": True,
        "route": "skip",
        "reason": "executor_disabled",
        "repo": "o/r",
        "issue": 1,
        "leftover": None,
        "leftover_issues": [],
    }


def test_department_receipt_never_merges() -> None:
    out = summarize({"route": "idle", "result": {"launched": "started"}})
    assert out["merged"] is False
    assert out["department"] == "executor"


def test_department_graph_is_list_nest_receipt() -> None:
    ids = [str(node["id"]) for node in _path("executor_department")["effectors"]]
    assert ids == [
        "list_open_issues",
        "run_executor_rows",
        "summarize_executor_department",
    ]
    row = [str(node["id"]) for node in _path("executor_row")["effectors"]]
    assert row == [
        "select_next_issue",
        "select_issue_do_row",
        "select_issue_executor",
        "issues_launch_pr",
        "summarize_executor_row",
    ]
    by_id = {node["id"]: node for node in _path("executor_row")["effectors"]}
    assert by_id["issues_launch_pr"]["when"] == {
        "upstream": "select_issue_executor",
        "path": "route",
        "equals": "do",
    }
    assert "pr_merge" not in row
    assert "issues_run_triage" not in row
