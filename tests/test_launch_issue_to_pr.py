"""issues_launch_pr: preserve route; live receipt consumes the occupied repo."""

from lokay.proc.launch_issue_to_pr import launch


CANDIDATE = {
    "ok": True,
    "route": "do",
    "repo": "mikolaj92/Temida",
    "issue": 5191,
    "leftover": 4,
    "leftover_issues": [
        {"repo": "mikolaj92/Temida", "issue": 5191},
        {"repo": "mikolaj92/Temida", "issue": 5190},
        {"repo": "mikolaj92/Fala", "issue": 186},
        {"repo": "mikolaj92/Posejdon", "issue": 46},
    ],
}


def test_live_receipt_does_not_overwrite_route_with_do(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.launch_issue_to_pr.detach_issue_to_pr",
        lambda **_k: {
            "ok": False,
            "reason": "receipt_unavailable",
            "error": "cannot reserve issue_to_pr receipt: cannot lock issue_to_pr receipts: existing issue_to_pr receipt is still live",
            "repo": "mikolaj92/Temida",
            "issue": 5191,
        },
    )
    out = launch(CANDIDATE, config_path=None)
    assert out["ok"] is True
    assert out["route"] == "failed"
    assert out["issue"] == 5191
    assert [row["issue"] for row in out["leftover_issues"]] == [186, 46]
    assert out["leftover"] == 2


def test_started_launch_drops_the_occupied_repo(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.launch_issue_to_pr.detach_issue_to_pr",
        lambda **_k: {
            "ok": True,
            "detached": True,
            "pid": 9,
            "repo": "mikolaj92/Temida",
            "issue": 5191,
        },
    )
    out = launch(CANDIDATE, config_path=None)
    assert out["route"] == "started"
    assert [row["issue"] for row in out["leftover_issues"]] == [186, 46]
    assert out["leftover"] == 2


def test_second_repo_waits_while_a_worker_is_still_live(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.launch_issue_to_pr.detach_issue_to_pr",
        lambda **_k: (_ for _ in ()).throw(AssertionError("must not detach")),
    )
    other = {**CANDIDATE, "repo": "mikolaj92/Fala", "issue": 186}
    out = launch(other, config_path=None, budget=2, live_count=1)
    assert out["route"] == "busy"
    assert out["reason"] == "global_occupancy"


def test_finished_worker_lets_the_next_repo_start(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.launch_issue_to_pr.detach_issue_to_pr",
        lambda **_k: {"ok": True, "detached": True, "pid": 9},
    )
    other = {**CANDIDATE, "repo": "mikolaj92/Fala", "issue": 186}
    out = launch(other, config_path=None, budget=2, live_count=0)
    assert out["route"] == "started"


def test_next_row_does_not_start_while_previous_worker_is_live(monkeypatch):
    from lokay.organ.executor_department_boundary import handle_executor_department

    monkeypatch.setattr(
        "lokay.proc.run_executor_row.run",
        lambda **_k: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    out = handle_executor_department(
        "run_executor_row_2",
        {},
        {
            "prepare_executor_rows": {"ok": True, "cap": 2, "spent": 0},
            "classify_executor_row_1": {
                "result": {"spent": 1, "launched": "started"},
            },
        },
        {},
    )
    assert out is not None
    assert out["route"] == "busy"
    assert out["reason"] == "global_occupancy"
