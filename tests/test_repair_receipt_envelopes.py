"""Real native repair -> department -> factory receipt, without live effects."""

import json
import sys
import tomllib
from contextlib import nullcontext

import pytest
from test_issue_triage_fala import base_effector

from lokay import graph_run
from lokay.pass_history import read_pass_history
from lokay.pass_receipt import read_pass_receipt
from lokay.proc import pr_repair_receipts as receipts


@pytest.mark.parametrize("published", [False, True])
def test_native_nested_repair_receipt_is_small_typed_evidence(tmp_path, monkeypatch, published):
    import fala
    from lokay.compose import pr_repair

    repo, pr, branch = "o/r", 9, "ai/fix/42-task"
    start, target = "a" * 40, "b" * 40
    selected = {
        "ok": True, "route": "repair", "repo": repo, "pr": pr,
        "branch": branch, "repair_kind": "ci", "repair_start_head_sha": start,
    }
    config = tmp_path / "config.yaml"
    config.write_text(f"mode: live\nstate:\n  path: {tmp_path / 'state.jsonl'}\nlimits:\n  max_request_changes_per_pr: 2\n")
    intent = receipts.build_push_intent(
        repo=repo, pr=pr, branch=branch, repair_kind="ci",
        start_head_sha=start, target_head_sha=target,
    )
    if published:
        receipts.prepare_push_intent(repo=repo, pr=pr, intent=intent, budget=2, state_dir=tmp_path)
        receipts.mark_push_attempted(repo=repo, pr=pr, intent_sha256=intent["intent_sha256"], state_dir=tmp_path)
    # Only host/external effects are substituted. Native transport, summary,
    # normalization, compose, department, confirmation and receipt are real.
    monkeypatch.setattr(pr_repair, "admit_live", lambda **_: {"route": "open"})
    monkeypatch.setattr("lokay.proc.probe_pr_state.probe", lambda **_: {
        "ok": True, "route": "open", "state": "OPEN", "head_ref": branch,
        "head_ref_sha": target, "head_repo": repo,
    })
    monkeypatch.setattr(graph_run, "path_journal_dir", lambda path_id, *a, **kw: tmp_path / path_id)
    monkeypatch.setattr(graph_run, "_review_credential_scope", lambda **_: nullcontext())
    monkeypatch.setattr("lokay.preflight.require_healthy", lambda *_: None)
    child = tmp_path / "repair.py"
    child.write_text(base_effector(f'''
from fala.sdk import declared_inputs
from lokay.fala_organ import _conduction_values, organ_envelope
from lokay.organ.repair_boundary import handle_repair_boundary
inputs = dict(declared_inputs(m))
if a == 'admit_pr_repair': v.update(route='open')
if a in {{'worktree_add', 'localize'}}: v.update(route='ready')
if a == 'run_agent': v.update(stdout_tail='evidence-only-' * 170000)
if a in {{'validate_initial_repair', 'select_initial_repair', 'finalize_repair_result'}}:
    v.update(route='repaired', evidence_kind='none')
if a in {{'select_evidence_repair', 'select_test_repair_result', 'select_repair_test_recheck'}}: v.update(route='not_applicable')
if a in {{'select_repair_test', 'finalize_repair_tests'}}: v.update(route='publish')
if a == 'checkpoint_repair_publication': v.update(route='checkpointed')
if a == 'push':
    v = organ_envelope(a, {{'ok': {published!r}, 'head_sha': {target!r},
        'reason': 'repair_push_worktree_dirty' if not {published!r} else '',
        'repair_push_intent_sha256': {intent['intent_sha256']!r}}})
if a == 'summarize_pr_repair':
    v = organ_envelope(a, handle_repair_boundary(a, inputs, _conduction_values(m),
        {{'repo': inputs['repo'], 'pr_number': inputs['pr']}}))
'''))
    parent = tmp_path / "factory.py"
    parent.write_text(base_effector(f'''
from lokay.organ.common import _conduction_values
from lokay.organ.factory import handle_factory
up = _conduction_values(m)
if a == 'factory_begin_host_gate': v.update(route='begin')
if a == 'factory_begin': v.update(state_path={str(tmp_path / 'state.jsonl')!r})
if a in {{'select_self_repair_department', 'select_issue_triage_department', 'select_executor_department'}}: v.update(route='skip')
if a == 'select_pr_triage_department': v.update(route='run')
if a == 'run_pr_triage_department': v.update(verdict='repair', repo={repo!r}, pr={pr!r})
if a == 'select_pr_repair_department': v = {selected!r}
if a == 'run_pr_repair_department': v = json.loads(Path({str(tmp_path / 'department.json')!r}).read_text())
if a in {{'record_pass', 'factory_pass_terminal'}}:
    v = handle_factory(a, {{}}, up, {{'cfg': [], 'live': [], 'repo': 'local/factory',
        'issue_number': None, 'pr_number': None, 'repair_mode': False, 'branch': None}})
'''))
    real_host = fala.host_run_package

    def host(**kw):
        nodes = tomllib.loads(kw["package_path"].read_text())["correlation_paths"][0]["effectors"]
        script = child if kw["path_id"] == "pr_repair" else parent
        return real_host(**kw, command_overrides={n["id"]: [sys.executable, str(script)] for n in nodes})

    monkeypatch.setattr(fala, "host_run_package", host)
    from lokay.proc.run_pr_repair_department import run

    department = run(selected, config_path=str(config), live=True)
    (tmp_path / "department.json").write_text(json.dumps(department))
    assert department["route"] == ("completed" if published else "fail_closed"), department.get("reason")
    assert len(json.dumps(department)) > 4_000_000
    full = department["repair"]
    journal = tmp_path / "pr_repair" / "state.sqlite"
    journal_before = journal.read_bytes()
    result = graph_run.run_path(path_id="factory_pass", repo="local/factory", live=False)
    receipt = read_pass_receipt(state_path=tmp_path / "state.jsonl")
    assert receipt is not None
    history = read_pass_history(state_path=tmp_path / "state.jsonl")
    for value in (result, receipt, history[-1]):
        evidence = value["pr_repair"]
        assert len(json.dumps(evidence)) < 3000
        assert all(not isinstance(v, (dict, list)) for k, v in evidence.items() if k != "trace")
        assert evidence["repo"] == repo
        assert evidence["pr"] == pr
        assert evidence["branch"] == branch
        assert evidence["repair_start_head_sha"] == start
        assert evidence["head_sha"] == target
        assert evidence["attempts"] == int(published)
        assert evidence["repaired"] is published
        assert evidence["published"] is published
        assert evidence["trace"] == {"db": str(journal), "run_id": full["run_id"], "path_id": "pr_repair"}
        assert value["health"] == ("repairing" if published else "pr_repair_blocked")
        assert value["outcome"] == "none"
        assert value["progress"] == int(published)
        assert value["idle"] is False
        if published:
            assert evidence["terminal"] == "publish"
        else:
            assert evidence["root_reason"] == "repair_push_worktree_dirty"
    assert len(json.dumps(receipt)) < 5000
    assert journal.read_bytes() == journal_before
    assert b"evidence-only-" in journal_before


@pytest.mark.parametrize("root_reason", [
    "repair_handoff_incomplete", "ci_repair_identity_invalid",
    "repair_kind_missing_or_invalid", "push_failed",
])
@pytest.mark.parametrize("structured_error", [False, True])
def test_native_summary_exception_preserves_nested_failure(tmp_path, root_reason, structured_error):
    from lokay.fala_organ import organ_envelope
    from lokay.proc.record_pass import run_record_pass
    from lokay.proc.summarize_pr_repair import summarize

    start, target = "a" * 40, "b" * 40
    handoff = {
        "repair_handoff_incomplete": {"kind": "review"},
        "ci_repair_identity_invalid": {"kind": "ci"},
        "repair_kind_missing_or_invalid": {},
        "push_failed": {"kind": "ci", "start_head_sha": start},
    }[root_reason]
    summary = summarize(
        final={"route": "publish"},
        push={"ok": root_reason != "push_failed", "head_sha": target},
        repo="o/r", pr=9, branch="ai/fix/42-task", repair_handoff=handoff,
    )
    assert summary["ok"] is False
    assert summary["result"]["reason"] == root_reason
    with pytest.raises(RuntimeError) as exc:
        organ_envelope("summarize_pr_repair", summary)
    message = f"adapter failed\nRuntimeError: {exc.value}"
    error = {"message": message} if structured_error else message
    trace = {"db": str(tmp_path / "state.sqlite"), "run_id": "repair-run", "path_id": "pr_repair"}
    normalized = graph_run.normalize_path_result({
        "ok": False, **trace,
        "fala": {"effector_results": {"summarize_pr_repair": {
            "status": "failed", "error": error,
        }}},
    })
    state_path = tmp_path / "state.jsonl"
    result = run_record_pass(
        begin={"state_path": str(state_path)},
        repair={
            "ok": True, "route": "fail_closed", "reason": "repair_push_not_confirmed",
            "repo": "o/r", "pr": 9, "branch": "ai/fix/42-task",
            "repair_start_head_sha": start, "attempts": 0, "repair": normalized,
        },
    )["result"]
    receipt = read_pass_receipt(state_path=state_path)
    assert receipt is not None
    for value in (result, receipt, read_pass_history(state_path=state_path)[-1]):
        evidence = value["pr_repair"]
        assert evidence["root_reason"] == root_reason
        assert evidence["head_sha"] == target
        assert evidence["reason"] == "repair_push_not_confirmed"
        assert evidence["repair_start_head_sha"] == start
        assert evidence["repo"] == "o/r"
        assert evidence["pr"] == 9
        assert evidence["branch"] == "ai/fix/42-task"
        assert evidence["attempts"] == 0
        assert evidence["ok"] is False
        assert evidence["repaired"] is False
        assert evidence["published"] is False
        assert evidence["terminal"] == "failed"
        assert evidence["trace"] == trace
        assert value["health"] == "pr_repair_blocked"
        assert value["progress"] == 0
        assert len(json.dumps(evidence)) < 3000
        assert all(not isinstance(v, (dict, list)) for k, v in evidence.items() if k != "trace")


def test_failed_transport_cannot_claim_nested_publication(tmp_path):
    from lokay.proc.record_pass import run_record_pass

    result = run_record_pass(
        begin={"state_path": str(tmp_path / "state.jsonl")},
        repair={
            "ok": True, "route": "completed", "repo": "o/r", "pr": 9,
            "repair_start_head_sha": "a" * 40,
            "repair": {"ok": False, "result": {
                "ok": True, "terminal": "publish", "repaired": True,
                "published": True, "head_sha": "b" * 40,
            }},
        },
    )["result"]
    assert result["health"] == "pr_repair_blocked"
    assert result["progress"] == 0
    assert result["pr_repair"]["published"] is False


@pytest.mark.parametrize("child", ["repair", "triage"])
def test_transport_fields_cannot_override_typed_domain_summary(child):
    from lokay.proc.record_pass import _pr_evidence

    domain = {"terminal": "publish", "repo": "o/r", "pr": 9,
              "head_sha": "b" * 40, "published": True, "attempts": 1}
    transport = {"terminal": {"logs": "x" * 2_000_000}, "repo": ["o/r"],
                 "pr": True, "head_sha": "x" * 2_000_000,
                 "published": "true", "attempts": {"count": 1}}
    summary = _pr_evidence({**transport, child: {"result": domain}}, child=child)
    assert summary == domain
