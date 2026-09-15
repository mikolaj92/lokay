from lokay.proc.run_pr_triage_subflow import CHILD_PATH, run


def test_named_slot_is_pr_triage() -> None:
    assert CHILD_PATH == "pr_triage"


def test_triage_receipt_preserves_complete_structured_review_handoff(monkeypatch) -> None:
    task = {
        "repo": "o/r", "type": "Issue", "state": "OPEN", "number": 42,
        "title": "task", "body": "full acceptance criteria", "url": "https://github.com/o/r/issues/42",
    }
    findings = [{
        "path": "src/a.py", "start_line": 3, "end_line": 4,
        "severity": "low", "category": "bug", "content": "complete finding text",
    }]
    decision = {
        "verdict": "request_changes", "task": task, "findings": findings,
        "reviewed_head_sha": "a" * 40, "task_identity_sha256": "b" * 64,
        "review_result_sha256": "c" * 64,
    }
    monkeypatch.setattr(
        "lokay.proc.run_pr_triage_subflow.run_path",
        lambda **_kwargs: {"ok": True, "repairable": True, "reason": "review_requested_changes", "review": decision},
    )

    out = run(
        {"route": "pr", "repo": "o/r", "pr": 9, "branch": "ai/fix/42-task"},
        config_path=None,
        live=False,
    )

    assert out["triage"]["review"] == decision
    assert out["triage"]["task"] == task
    assert out["triage"]["findings"] == findings
    assert out["triage"]["reviewed_head_sha"] == "a" * 40
    assert out["triage"]["task_identity_sha256"] == "b" * 64
    assert out["triage"]["review_result_sha256"] == "c" * 64


def test_ci_repair_handoff_is_lifted_from_normalized_pr_triage_path(monkeypatch) -> None:
    head = "d" * 40
    monkeypatch.setattr(
        "lokay.proc.run_pr_triage_subflow.run_path",
        lambda **_kwargs: {
            "ok": True,
            "pr_checks": {"head_sha": head},
            "classify_pr_triage_checks": {"head_sha": head, "route": "repair"},
            "select_pr_triage_outcome": {
                "route": "repair", "repair_kind": "ci", "head_sha": head,
                "repairable": True, "reason": "checks_failed",
            },
            "pr_repair_verdict": {
                "route": "repair", "repair_kind": "ci", "head_sha": head,
                "repairable": True, "reason": "checks_failed",
                "task": {}, "findings": [],
            },
            "terminal": {
                "summarize_pr_triage": {
                    "ok": True,
                    "result": {"repairable": True, "repair_kind": "ci", "head_sha": head},
                },
            },
        },
    )

    out = run(
        {"route": "pr", "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x"},
        config_path=None, live=False,
    )

    assert out["triage"]["repairable"] is True
    assert out["triage"]["repair_kind"] == "ci"
    assert out["triage"]["head_sha"] == head


def test_department_runner_keeps_reconciliation_inside_authored_child(monkeypatch) -> None:
    seen: list[dict] = []

    def fake(**kwargs):
        seen.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr("lokay.proc.run_pr_triage_department.run_path", fake)
    from lokay.proc.run_pr_triage_department import run as run_department

    run_department(pass_dir="/tmp/pass", config_path="config.yaml", live=True)

    assert seen[0]["extra_inputs"] == {"pass_dir": "/tmp/pass"}


def test_launches_child_path_only(monkeypatch) -> None:
    seen: list[dict] = []

    def fake(**kwargs):
        seen.append(kwargs)
        return {"ok": True, "merged": True}

    monkeypatch.setattr("lokay.proc.run_pr_triage_subflow.run_path", fake)
    out = run(
        {"route": "pr", "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x"},
        config_path=None,
        live=False,
    )
    assert out["route"] == "completed"
    assert out["triage"]["merged"] is True
    assert out["triage"]["repairable"] is False
    assert seen == [
        {
            "path_id": "pr_triage",
            "repo": "o/r",
            "pr": 9,
            "branch": "ai/fix/9-x",
            "config_path": None,
            "live": False,
        }
    ]
