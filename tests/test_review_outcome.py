"""PR review domain outcomes stay separate from execution/cache metadata."""

from lokay.proc.review_repair_gate import route_review_repair
from lokay.proc.review_terminal import terminal_review


def test_request_changes_without_durable_handoff_fails_closed():
    result = route_review_repair({
        "skipped": True, "reason": "already_reviewed_head",
        "decision": {"verdict": "request_changes", "secrets": False},
    })
    assert result["route"] == "fail_closed"
    assert result["reason"] == "review_repair_handoff_incomplete"


def test_request_changes_routes_to_repair_when_durable_handoff_is_complete():
    result = route_review_repair({
        "skipped": True, "reason": "already_reviewed_head",
        "decision": {
            "verdict": "request_changes", "secrets": False,
            "task": {"repo": "o/r", "type": "Issue", "state": "OPEN"},
            "findings": [{"path": "a.py"}], "reviewed_head_sha": "a" * 40,
            "task_identity_sha256": "b" * 64, "review_result_sha256": "c" * 64,
        },
    })
    assert result["route"] == "repair"


def test_request_changes_cap_routes_to_terminal_human():
    result = route_review_repair({
        "escalated": True,
        "decision": {"verdict": "request_changes", "secrets": False},
    })
    assert result["route"] == "fail_closed"


def test_secret_request_changes_routes_to_terminal_human():
    result = route_review_repair({
        "decision": {"verdict": "request_changes", "secrets": True},
    })
    assert result["route"] == "fail_closed"


def test_manual_terminal_is_a_domain_result():
    result = terminal_review(verdict="fail_closed", reason="review_needs_human")
    assert result["terminal"] is True
    assert result["verdict"] == "fail_closed"
    assert result["needs_review"] is True


def test_review_manual_keeps_classified_incomplete_reason():
    from lokay.organ.pr_outcome import handle_pr_outcome
    from lokay.proc.walk_pr_leftover import classify_occupancy, leftover_after

    out = handle_pr_outcome(
        "review_manual", {},
        {"publish_pr_review": {
            "decision": {"verdict": "fail_closed"},
            "reason": "review_plugin_failed",
        }},
        {"repo": "mikolaj92/splot", "pr_number": 56, "branch": "ai/fix/41-x", "live": True},
    )
    assert out["reason"] == "review_plugin_failed"
    assert out["reason"] != "review_fail_closed"
    occupancy = classify_occupancy({
        "route": "completed", "verdict": "feedback", "reason": out["reason"],
    })
    assert occupancy == {"class": "incomplete", "keep": True}
    kept = leftover_after(
        {"repo": "mikolaj92/splot", "pr": 56, "head_sha": "908e0d03",
         "route": "pr", "leftover_prs": [{"repo": "o/r", "pr": 41, "head_sha": "aa"}]},
        {"route": "completed", "verdict": "feedback", "reason": out["reason"]},
    )
    assert [row["pr"] for row in kept] == [56, 41]


def test_review_manual_keeps_complete_reject_reason():
    from lokay.organ.pr_outcome import handle_pr_outcome
    from lokay.proc.walk_pr_leftover import classify_occupancy, leftover_after

    out = handle_pr_outcome(
        "review_manual", {},
        {"publish_pr_review": {
            "decision": {"verdict": "fail_closed"},
            "reason": "ocr_contract_rejected: review has warnings",
        }},
        {"repo": "a/b", "pr_number": 7, "branch": "ai/fix/7-x", "live": True},
    )
    assert out["reason"].startswith("ocr_contract_rejected")
    occupancy = classify_occupancy({
        "route": "completed", "verdict": "feedback", "reason": out["reason"],
    })
    assert occupancy == {"class": "complete_reject", "keep": False}
    rest = leftover_after(
        {"repo": "a/b", "pr": 7, "head_sha": "aa", "route": "pr",
         "leftover_prs": [{"repo": "o/r", "pr": 1, "head_sha": "bb"}]},
        {"route": "completed", "verdict": "feedback", "reason": out["reason"]},
    )
    assert [row["pr"] for row in rest] == [1]


def test_pr_repair_verdict_preserves_ci_only_repairs_without_review_evidence():
    from lokay.organ.pr_outcome import handle_pr_outcome

    out = handle_pr_outcome(
        "pr_repair_verdict", {},
        {
            "select_pr_triage_outcome": {
                "route": "repair", "repair_kind": "ci", "reason": "checks_failed",
                "head_sha": "a" * 40,
            },
            "publish_pr_review": {"decision": {"verdict": "not_applicable"}},
        },
        {"repo": "a/b", "pr_number": 7, "branch": "ai/fix/7-x", "live": False},
    )

    assert out["route"] == "repair"
    assert out["repairable"] is True
    assert out["repair_kind"] == "ci"
    assert out["task"] == {} and out["findings"] == []


def test_pr_outcome_handler_routes_reused_request_changes(monkeypatch):
    from lokay.organ.pr_outcome import handle_pr_outcome
    decision = {
        "verdict": "request_changes", "secrets": False,
        "task": {"repo": "a/b", "type": "Issue", "state": "OPEN"},
        "findings": [{"path": "a.py"}], "reviewed_head_sha": "a" * 40,
        "task_identity_sha256": "b" * 64, "review_result_sha256": "c" * 64,
    }
    out = handle_pr_outcome(
        "review_repair_gate", {},
        {
            "select_pr_triage_outcome": {
                "route": "repair", "repair_kind": "review",
                "repair_start_head_sha": "a" * 40,
            },
            "publish_pr_review": {"execution": {"source": "cache"}, "decision": decision},
        },
        {"repo": "a/b", "pr_number": 7, "branch": "ai/fix/7-x", "live": []},
    )
    assert out["route"] == "repair"
    assert out["reviewed_head_sha"] == "a" * 40


def test_review_repair_verdict_rejects_start_head_drift():
    from lokay.organ.pr_outcome import handle_pr_outcome

    decision = {
        "verdict": "request_changes", "secrets": False,
        "task": {"repo": "a/b", "type": "Issue", "state": "OPEN"},
        "findings": [{"path": "a.py"}], "reviewed_head_sha": "a" * 40,
        "task_identity_sha256": "b" * 64, "review_result_sha256": "c" * 64,
    }
    out = handle_pr_outcome(
        "pr_repair_verdict", {},
        {
            "select_pr_triage_outcome": {
                "route": "repair", "repair_kind": "review",
                "repair_start_head_sha": "d" * 40,
            },
            "publish_pr_review": {"decision": decision},
        },
        {"repo": "a/b", "pr_number": 7, "branch": "ai/fix/7-x", "live": False},
    )

    assert out["route"] == "fail_closed"
    assert out["reason"] == "review_repair_handoff_incomplete"


def test_parent_pr_repair_slot_forwards_review(monkeypatch, tmp_path):
    from lokay.proc import run_parent_pr_repair_subflow as module
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""mode: dry-run
state:
  path: {tmp_path / "state.jsonl"}
repos:
  - name: a/b
    clone_path: {tmp_path / "r"}
    enabled: true
""",
        encoding="utf-8",
    )
    calls = []
    task = {"repo": "a/b", "type": "Issue", "state": "OPEN", "number": 7, "title": "task", "body": "criteria"}
    finding = {"path": "src/a.py", "start_line": 1, "end_line": 1, "content": "fix"}
    import hashlib
    import json
    task_digest = hashlib.sha256(json.dumps(task, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    review = {
        "verdict": "request_changes", "task": task, "findings": [finding],
        "reviewed_head_sha": "a" * 40, "task_identity_sha256": task_digest,
        "review_result_sha256": "c" * 64,
    }
    monkeypatch.setattr(
        module, "compose_pr_repair",
        lambda **kwargs: calls.append(kwargs) or {"ok": True, "result": {
            "repo": "a/b", "pr": 7, "terminal": "publish", "repaired": True,
            "published": True, "head_sha": "d" * 40, "branch": "ai/fix/7-x",
            "reviewed_head_sha": "a" * 40,
            "task": task, "findings": [finding], "task_identity_sha256": task_digest,
            "review_result_sha256": "c" * 64,
        }},
    )
    out = module.run(
        {"repo": "a/b", "pr": 7, "branch": "ai/fix/7-x", "review": review,
         "task": task, "findings": [finding], "reviewed_head_sha": "a" * 40,
         "task_identity_sha256": task_digest, "review_result_sha256": "c" * 64,
         "repair_kind": "review"},
        config_path=str(cfg), live=False,
    )
    assert out["route"] == "planned"
    assert out["attempts"] == 0
    assert calls[0]["task"] == task
    assert calls[0]["findings"] == [finding]
    assert calls[0]["review_result_sha256"] == "c" * 64


def test_pr_repair_subflow_forwards_complete_repair_handoff(monkeypatch):
    from lokay.proc import pr_repair_subflow as module

    calls = []
    monkeypatch.setattr(
        module, "compose_pr_repair",
        lambda **kwargs: calls.append(kwargs) or {"ok": True},
    )
    review = {"decision": {"verdict": "request_changes"}, "head_sha": "abc"}
    task = {"repo": "a/b", "number": 7, "title": "original task"}
    findings = [{"path": "src/a.py", "content": "fix this"}]
    out = module.run_pr_repair_subflow(
        config_path="cfg", repo="a/b", pr=7, branch="ai/fix/7-x",
        review=review, task=task, findings=findings,
        reviewed_head_sha="a" * 40, task_identity_sha256="b" * 64,
        review_result_sha256="c" * 64, repair_kind="review", live=True,
    )

    assert out["ok"] is True
    assert calls == [{
        "config_path": "cfg", "repo": "a/b", "pr_number": 7,
        "branch": "ai/fix/7-x", "review": review, "task": task,
        "findings": findings, "reviewed_head_sha": "a" * 40,
        "task_identity_sha256": "b" * 64, "review_result_sha256": "c" * 64,
        "repair_kind": "review", "repair_start_head_sha": "", "live": True,
    }]
