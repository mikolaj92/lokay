"""pr_triage department: review + merge. repair is a verdict, not a child."""

import tomllib
from pathlib import Path

from lokay.proc.select_pr_repair_department import select as select_repair
from lokay.proc.select_pr_triage_verdict import classify, select
from lokay.proc.summarize_pr_triage_department import summarize


def _path(path_id: str) -> dict:
    package = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "fala/lokay.fala-package.toml").read_text(
            encoding="utf-8"
        )
    )
    return next(row for row in package["correlation_paths"] if row["id"] == path_id)


def test_verdict_is_merge_feedback_or_repair() -> None:
    picked = {"route": "pr", "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x"}
    assert select(picked, {"triage": {"merged": True}})["verdict"] == "merge"
    assert select(picked, {"triage": {"repairable": True, "reason": "red_ci"}})[
        "verdict"
    ] == "repair"
    assert select(picked, {"triage": {"waiting": True}})["verdict"] == "feedback"
    assert select(picked, {"triage": {}})["verdict"] == "feedback"
    assert "run_pr_repair" not in select(picked, {"triage": {"repairable": True}})


def test_classify_does_not_start_repair() -> None:
    facts = classify({"triage": {"repairable": True, "reason": "request_changes"}})
    assert facts["repairable"] is True
    assert "started" not in facts


def test_receipt_never_starts_repair() -> None:
    out = summarize(
        {"route": "pr", "pr": 9},
        {"route": "completed", "triage": {"repairable": True}},
        {"verdict": "repair", "repairable": True, "pr": 9},
    )
    assert out["repair_started"] is False
    assert out["verdict"] == "repair"
    assert out["department"] == "pr_triage"
    assert out["result"]["verdict"] == "repair"
    assert out["result"]["repair_started"] is False
    assert "run_pr_repair" not in out["result"]


def test_parent_repair_reads_the_verdict() -> None:
    out = select_repair(
        {
            "triage": {
                "repairable": True,
                "reason": "red_ci",
                "review": {"verdict": "request_changes"},
            },
            "repo": "o/r",
            "pr": 9,
            "branch": "ai/fix/9-x",
        },
        enabled=True,
        triage_ran=True,
    )
    assert out["route"] == "repair"
    assert out["review"] == {"verdict": "request_changes"}
    assert select_repair({}, enabled=True, triage_ran=True)["reason"] == "no_triage_verdict"


def test_parent_repair_reads_normalized_sieve_envelope() -> None:
    lifted = {
        "ok": True,
        "engine": "fala",
        "path_id": "pr_triage_department",
        "verdict": "repair",
        "triage": {"repairable": True, "reason": "red_ci"},
        "repo": "o/r",
        "pr": 9,
        "branch": "ai/fix/9-x",
        "repair_started": False,
    }
    out = select_repair(lifted, enabled=True, triage_ran=True)
    assert out["route"] == "repair"
    assert out["repo"] == "o/r" and out["pr"] == 9
    assert out["branch"] == "ai/fix/9-x"


def test_disabled_repair_does_not_touch_sieve_feedback() -> None:
    receipt = summarize(
        {"route": "pr", "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x"},
        {"route": "completed", "triage": {"repairable": True, "reason": "red_ci"}},
        {"verdict": "repair", "repairable": True, "repo": "o/r", "pr": 9},
    )
    out = select_repair(receipt, enabled=False, triage_ran=True)
    assert out["route"] == "skip"
    assert out["reason"] == "pr_repair_disabled"
    assert receipt["repair_started"] is False


def test_department_graph_has_no_repair_child() -> None:
    ids = [str(node["id"]) for node in _path("pr_triage_department")["effectors"]]
    assert ids == [
        "list_pr_sieve",
        "select_pr_sieve",
        "run_pr_sieve",
        "select_pr_triage_verdict",
        "summarize_pr_triage_department",
    ]
    assert "run_pr_repair_subflow" not in ids
    assert "select_pr_repair" not in ids
    assert "run_pr_triage_subflow" not in ids
    by_id = {node["id"]: node for node in _path("pr_triage_department")["effectors"]}
    assert by_id["run_pr_sieve"]["when"] == {
        "upstream": "select_pr_sieve",
        "path": "route",
        "equals": "pr",
    }
