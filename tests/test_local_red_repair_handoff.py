"""Keep review evidence distinct from repair authority across the native child."""

import hashlib
import json

import pytest
from test_issue_triage_fala import base_effector, run_graph

from lokay.graph_run import normalize_path_result
from lokay.proc import run_pr_triage_subflow
from lokay.proc.select_pr_repair_department import select as authorize
from lokay.proc.select_pr_triage_verdict import select as select_verdict
from lokay.proc.summarize_pr_triage_department import summarize


@pytest.mark.parametrize("review_verdict", ["approve", "request_changes"])
def test_native_review_to_repair_department(tmp_path, monkeypatch, review_verdict):
    head = "a" * 40
    target = {"repo": "o/r", "pr": 9, "branch": "ai/fix/42-task"}
    task = {
        "repo": "o/r", "type": "Issue", "state": "OPEN", "number": 42,
        "title": "task", "body": "full acceptance criteria",
        "url": "https://github.com/o/r/issues/42",
    }
    decision = {
        "verdict": review_verdict, "task": task,
        "findings": [] if review_verdict == "approve" else [{
            "path": "src/a.py", "start_line": 3, "end_line": 4,
            "severity": "low", "category": "bug", "content": "complete finding text",
        }],
        "reviewed_head_sha": head,
        "task_identity_sha256": hashlib.sha256(json.dumps(
            task, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest(),
        "review_result_sha256": "b" * 64,
    }
    # Only external facts/effects are substituted. Native Fala conducts the real
    # checks classifier, review gate, outcome, repair verdict and child summary.
    body = base_effector(
        f"""from lokay.organ.common import _conduction_values
from lokay.organ.pr_outcome import handle_pr_outcome
v.update(route='fixture')
if a=='pr_checks':v.update(status='passed',head_sha={head!r})
if a=='resolve_sha_review':v.update(route='cached')
if a=='publish_pr_review':v.update(decision={decision!r})
if a=='worktree_add':v.update(route='ready')
if a=='test_local':v.update(skipped=False,passed=False)
real = handle_pr_outcome(a, {{}}, _conduction_values(m), {{}})
if real is not None:v=real"""
    )
    native = run_graph(tmp_path, body, "local-red-handoff", path_id="pr_triage")
    child = normalize_path_result({"ok": True, "path_id": "pr_triage", "fala": native})
    assert child["ok"], json.dumps(child, indent=2)
    nodes = native["effector_results"]
    assert nodes["pr_merge"]["status"] == "skipped"
    assert nodes["test_local"]["status"] == (
        "succeeded" if review_verdict == "approve" else "skipped"
    )
    expected_kind = "ci" if review_verdict == "approve" else "review"
    outcome = child["terminal"]["select_pr_triage_outcome"]
    assert outcome["repair_kind"] == expected_kind
    assert outcome["reason"] == (
        "test_local_failed" if review_verdict == "approve" else "review_requested_changes"
    )

    # Feed the actual native result through the production parent wrapper;
    # substituting run_path avoids any live GitHub/review/agent invocation.
    monkeypatch.setattr(run_pr_triage_subflow, "run_path", lambda **_kwargs: child)
    parent = run_pr_triage_subflow.run(target, config_path=None, live=False)
    picked = {"route": "pr", **target, "head_sha": head}
    recovery = {"route": "review"}
    verdict = select_verdict(picked, parent, recovery)
    receipt = summarize(picked, parent, verdict, recovery)
    selected = authorize(receipt, enabled=True, triage_ran=True, state_dir=tmp_path / "receipts")
    assert selected["route"] == "repair", selected
    assert selected["repair_kind"] == expected_kind
    assert selected["repair_start_head_sha"] == head
    assert {key: selected[key] for key in target} == target

    fields = {
        "task": {}, "findings": [], "reviewed_head_sha": "",
        "task_identity_sha256": "", "review_result_sha256": "",
    }
    if expected_kind == "review":
        fields = {key: decision[key] for key in fields}
    for stage in (
        child["terminal"]["pr_repair_verdict"], child["terminal"]["summarize_pr_triage"]["result"],
        parent["triage"], verdict, receipt, receipt["triage"], selected,
    ):
        assert {key: stage[key] for key in fields} == fields
    assert parent["triage"]["review"] == decision  # evidence, not repair authority
    assert selected["review"] == decision
    assert receipt["repair_started"] is False
    assert not list((tmp_path / "receipts").rglob("*.json"))  # no repair spent

    if expected_kind == "ci":
        # Empty handoff authority must not mean accepting nonempty CI fields.
        for field, value in {
            **decision, "findings": [{"content": "must not enter CI repair"}],
        }.items():
            if field not in fields:
                continue
            contaminated = {**receipt, field: value}
            contaminated.pop("result")
            denied = authorize(
                contaminated, enabled=True, triage_ran=True, state_dir=tmp_path / "receipts",
            )
            assert denied["route"] == "fail_closed"
            assert denied["reason"] == "ci_repair_contains_review_handoff"
