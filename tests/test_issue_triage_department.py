"""issue_triage department: sieve only. Marks/children, zero ai/fix."""

import tomllib
from pathlib import Path

from lokay.proc.select_issue_sieve import classify_sieve, select
from lokay.proc.summarize_issue_triage_department import summarize


def _path(path_id: str) -> dict:
    package = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "fala/lokay.fala-package.toml").read_text(
            encoding="utf-8"
        )
    )
    return next(row for row in package["correlation_paths"] if row["id"] == path_id)


def test_sieve_routes_do_skip_park_human_split_intake() -> None:
    assert classify_sieve(
        {"route": "completed", "triage": {"result": {"implementable": True}}},
        {"route": "issue"},
    )["route"] == "do"
    assert classify_sieve(
        {
            "route": "completed",
            "triage": {"decision": {"verdict": "skip", "reason": "sito_nie_robic"}},
        },
        {"route": "issue"},
    )["route"] == "skip"
    assert classify_sieve(
        {"route": "completed", "triage": {"decision": {"verdict": "close"}}},
        {"route": "issue"},
    )["route"] == "park"
    assert classify_sieve(
        {"route": "completed", "triage": {"decision": {"verdict": "needs_human"}}},
        {"route": "issue"},
    )["route"] == "human"
    assert classify_sieve(
        {
            "route": "completed",
            "triage": {"decision": {"verdict": "needs_human", "reason": "oversized_split"}},
        },
        {"route": "issue"},
    )["route"] == "split"
    assert classify_sieve(
        {
            "route": "completed",
            "triage": {"decision": {"verdict": "skip", "reason": "intake_superseded"}},
        },
        {"route": "issue"},
    )["route"] == "intake"


def test_sieve_select_never_launches() -> None:
    out = select(
        {"route": "issue", "repo": "o/r", "issue": 3},
        {"route": "completed", "triage": {"result": {"implementable": True}}},
        {"issues": [{"repo": "o/r", "issue": 3}, {"repo": "o/r", "issue": 4}]},
    )
    assert out["route"] == "do"
    assert "launched" not in out
    assert out["leftover"] == 1


def test_department_receipt_has_zero_ai_fix() -> None:
    out = summarize({"route": "idle", "result": {"launched": "started", "leftover": 0}})
    assert out["launched"] is None
    assert out["result"]["launched"] is None
    assert out["department"] == "issue_triage"


def test_department_graph_has_no_launch() -> None:
    ids = [str(node["id"]) for node in _path("issue_triage_department")["effectors"]]
    assert ids == [
        "list_open_issues",
        "run_issue_sieve_rows",
        "summarize_issue_triage_department",
    ]
    row = [str(node["id"]) for node in _path("issue_sieve_row")["effectors"]]
    assert "issues_launch_pr" not in row
    assert "select_issue_executor" not in row
    assert "run_issue_sieve_split" in row
    assert "run_issue_sieve_intake" in row
    assert "select_issue_sieve" in row


def test_sieve_row_skips_split_and_intake_unless_selected() -> None:
    by_id = {node["id"]: node for node in _path("issue_sieve_row")["effectors"]}
    assert by_id["run_issue_sieve_split"]["when"] == {
        "upstream": "select_issue_sieve",
        "path": "route",
        "equals": "split",
    }
    assert by_id["run_issue_sieve_intake"]["when"] == {
        "upstream": "select_issue_sieve",
        "path": "route",
        "equals": "intake",
    }
    assert by_id["issues_run_triage"]["when"]["equals"] == "issue"
