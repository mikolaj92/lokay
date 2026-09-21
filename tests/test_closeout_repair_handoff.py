"""Explicit single-PR closeout, not the daemon's durable repair department."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from lokay.organ.pr_closeout_boundary import handle_pr_closeout

SHA = "a" * 40


def inputs():
    return {"live": True, "selected": {
        "repo": "o/r", "pr": {"number": 7, "head_ref": "ai/fix/7-x"},
        "repair_budget": 1, "policy": {"executor_enabled": True, "merge_enabled": True, "require_checks": True},
    }}


def review():
    task = {"repo": "o/r", "type": "Issue", "state": "OPEN", "number": 7,
            "title": "Task", "body": "Acceptance"}
    return {"verdict": "request_changes", "task": task,
            "findings": [{"path": "src/a.py", "start_line": 1, "end_line": 1,
                          "severity": "high", "category": "bug", "content": "Fix it"}],
            "reviewed_head_sha": SHA,
            "task_identity_sha256": hashlib.sha256(json.dumps(
                task, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()).hexdigest(), "review_result_sha256": "b" * 64}


def handoff(kind, *, data=None, decision=None, start=None):
    data = data or inputs()
    up = {}
    def call(atom):
        out = handle_pr_closeout(atom, data, up, {})
        up[atom] = out
        return out
    call("inspect_closeout_pr")
    up["read_closeout_issue"] = {"route": "open_or_unknown"}
    call("classify_closeout_gate")
    if kind == "ci":
        up["read_closeout_checks"] = {"route": "route", "checks": {
            "ok": True, "status": "failed", "head_sha": SHA if start is None else start}}
        call("route_closeout_checks")
        auth, run = "authorize_closeout_repair", "run_closeout_repair"
    else:
        tri = {"ok": True, "skipped": True, "repairable": True,
               "repair_kind": "review", "review": decision if decision is not None else review()}
        if start is not None:
            tri["repair_start_head_sha"] = start
        up["run_closeout_triage"] = {"triage": tri}
        call("classify_closeout_triage")
        auth, run = "authorize_closeout_review_repair", "run_closeout_review_repair"
    call(auth)
    return call, up, auth, run


@pytest.fixture
def compose_boundary(monkeypatch, tmp_path):
    """Only external admission/state boundaries are replaced; compose is real."""
    from lokay.compose import pr_repair
    monkeypatch.setattr(pr_repair, "load_config", lambda _: SimpleNamespace(mode="live", state_path=tmp_path / "state"))
    monkeypatch.setattr(pr_repair, "admit_live", lambda **_: {"route": "open"})
    monkeypatch.setattr(pr_repair, "append_event", lambda *_: None)
    return pr_repair


@pytest.mark.parametrize("kind", ["ci", "review"])
def test_closeout_identity_reaches_real_compose(kind, compose_boundary, monkeypatch):
    seen = {}
    monkeypatch.setattr(compose_boundary, "run_path", lambda **kw: seen.update(kw) or {
        "ok": False, "terminal": "blocked", "reason": "repair_start_identity_missing"})
    call, up, auth, run = handoff(kind)
    assert up[auth]["route"] == "repair"
    result = call(run)
    child = seen["extra_inputs"]
    assert child["repair_kind"] == kind
    assert child["head_sha"] == SHA
    expected = review() if kind == "review" else {}
    for key, empty in (("task", {}), ("findings", []), ("reviewed_head_sha", ""),
                       ("task_identity_sha256", ""), ("review_result_sha256", "")):
        assert child[key] == expected.get(key, empty)
    assert result["repair_used"] == 0
    assert call("select_closeout_repair_result")["repair_used"] == 0
    assert call("finalize_closeout_pr")["repair_budget"] == 1


@pytest.mark.parametrize("control", ["dry_run", "ci_dry_run", "disabled", "budget", "branch", "ci_sha", "review_sha", "findings", "digest", "conflict"])
def test_closeout_no_start_controls(control, compose_boundary, monkeypatch):
    monkeypatch.setattr(compose_boundary, "run_path", lambda **_: pytest.fail("must not start child"))
    data, decision, start, kind = inputs(), review(), None, "review"
    if control in {"dry_run", "ci_dry_run"}: data["live"] = False
    if control == "ci_dry_run": kind = "ci"
    if control == "disabled": data["selected"]["policy"]["executor_enabled"] = False
    if control == "budget": data["selected"]["repair_budget"] = 0
    if control == "branch": data["selected"]["pr"]["head_ref"] = ""
    if control == "ci_sha": kind, start = "ci", ""
    if control == "review_sha": decision["reviewed_head_sha"] = ""
    if control == "findings": decision["findings"] = []
    if control == "digest": decision["task_identity_sha256"] = "c" * 64
    if control == "conflict": start = "c" * 40
    call, up, auth, run = handoff(kind, data=data, decision=decision, start=start)
    assert up[auth]["route"] != "repair"
    assert call(run)["repair_used"] == 0


@pytest.mark.parametrize("child,used", [
    ({"ok": False, "error": "host unavailable"}, 0),
    ({"ok": True, "result": {"ok": False, "terminal": "blocked"}}, 0),
    ({"ok": True, "skipped": True, "reason": "pr_already_merged"}, 0),
    ({"ok": True, "terminal": "not_applicable"}, 0),
    ({"ok": True, "repaired": True, "published": True, "head_sha": "c" * 40}, 1),
    ({"ok": True, "steps": [{"step": "run_agent", "status": "completed", "returncode": 0}]}, 1),
    ({"ok": False, "steps": [{"step": "run_agent", "status": "failed", "returncode": 1}]}, 1),
    ({"ok": False, "steps": [{"step": "run_agent", "status": "failed", "error": "spawn failed"}]}, 0),
    ({"ok": False, "steps": [{"step": "run_agent", "status": "failed", "error": json.dumps({"ok": False, "reason": "agent_failed", "returncode": 1})}]}, 1),
    ({"ok": True, "steps": [{"step": "run_agent", "status": "timeout", "returncode": -1, "timed_out": True}]}, 1),
    ({"ok": True, "steps": [{"step": "run_agent", "status": "planned"}]}, 0),
])
def test_cli_attempt_counts_effect_or_executed_correction_not_infrastructure(child, used, compose_boundary, monkeypatch):
    monkeypatch.setattr(compose_boundary, "run_path", lambda **_: child)
    call, _, _, run = handoff("ci")
    assert call(run)["repair_used"] == used


def test_closeout_compose_exception_does_not_spend_budget(compose_boundary, monkeypatch):
    def unavailable(**_):
        raise RuntimeError("native host unavailable")
    monkeypatch.setattr(compose_boundary, "run_path", unavailable)
    call, _, _, run = handoff("ci")
    out = call(run)
    assert out["repair"]["ok"] is False
    assert out["repair_used"] == 0


def test_closeout_admission_skip_does_not_start_native_child(compose_boundary, monkeypatch):
    monkeypatch.setattr(compose_boundary, "admit_live", lambda **_: {
        "route": "skip", "reason": "pr_already_merged"})
    monkeypatch.setattr(compose_boundary, "run_path", lambda **_: pytest.fail("merged PR"))
    call, _, _, run = handoff("review")
    out = call(run)
    assert out["repair"]["reason"] == "pr_already_merged"
    assert out["repair_used"] == 0


@pytest.mark.parametrize("kind", ["ci", "review"])
@pytest.mark.parametrize("outcome", ["blocked", "attempted", "agent_failed"])
def test_closeout_compose_native_child_worktree_handoff(kind, outcome, compose_boundary, monkeypatch, tmp_path):
    """Run actual compose + run_path + native child; replace all effectors' I/O."""
    import fala
    from contextlib import nullcontext
    from lokay import graph_run
    from test_issue_triage_fala import base_effector
    import sys
    import tomllib

    capture = tmp_path / "worktree.json"
    body = base_effector('''
from fala.sdk import declared_inputs
from lokay.fala_organ import _conduction_values, organ_envelope
from lokay.organ.implement import handle_implement
from lokay.organ.repair_boundary import handle_repair_boundary
inputs = dict(declared_inputs(m))
if a == 'admit_pr_repair': v.update(route='open')
if a == 'worktree_add':
    calls = []
    v = handle_implement(a, inputs, {}, {
        'cfg': [], 'live': [], 'repo': inputs['repo'], 'pr_number': inputs['pr'],
        'issue_number': None, 'repair_mode': True, 'branch': inputs['branch'],
        'run_atom_main': lambda main, argv: calls.append(argv) or {
            'ok': True, 'route': WORKTREE_ROUTE, 'reason': 'repair_start_identity_missing'}})
    Path(CAPTURE).write_text(json.dumps({'inputs': inputs, 'argv': calls[0]}))
if a == 'localize': v.update(route='ready')
if a == 'run_agent':
    v.update(status='completed', returncode=0)
    if OUTCOME == 'agent_failed':
        v = organ_envelope(a, {'ok': False, 'reason': 'agent_failed', 'returncode': 1})
if a in {'validate_initial_repair', 'select_initial_repair', 'finalize_repair_result'}:
    v.update(route='fail_closed', evidence_kind='none')
if a in {'select_evidence_repair', 'select_repair_test', 'select_test_repair_result', 'select_repair_test_recheck', 'finalize_repair_tests'}:
    v.update(route='not_applicable')
if a == 'summarize_pr_repair':
    v = organ_envelope(a, handle_repair_boundary(a, inputs, _conduction_values(m),
        {'repo': inputs['repo'], 'pr_number': inputs['pr']}))
'''.replace("CAPTURE", repr(str(capture)))
       .replace("WORKTREE_ROUTE", repr("missing" if outcome == "blocked" else "ready"))
       .replace("OUTCOME", repr(outcome)))
    effector = tmp_path / "effector.py"
    effector.write_text(body)
    real_host = fala.host_run_package
    def host(**kw):
        package = tomllib.loads(kw["package_path"].read_text())
        nodes = package["correlation_paths"][0]["effectors"]
        return real_host(**kw, command_overrides={n["id"]: [sys.executable, str(effector)] for n in nodes})
    monkeypatch.setattr(fala, "host_run_package", host)
    monkeypatch.setattr(graph_run, "path_journal_dir", lambda *a, **kw: tmp_path / "journal")
    monkeypatch.setattr(graph_run, "_review_credential_scope", lambda **_: nullcontext())
    monkeypatch.setattr("lokay.preflight.require_healthy", lambda *_: None)
    call, _, _, run = handoff(kind)
    result = call(run)
    captured = json.loads(capture.read_text())
    child = captured["inputs"]
    assert child["repair_kind"] == kind
    assert child["head_sha"] == SHA
    argv = captured["argv"]
    assert argv[argv.index("--repair-start-head-sha") + 1] == SHA
    if kind == "review":
        for key in ("task", "findings", "reviewed_head_sha", "task_identity_sha256", "review_result_sha256"):
            assert child[key] == review()[key]
    assert result["repair_used"] == int(outcome != "blocked")
    steps = {s["step"]: s for s in result["repair"]["steps"]}
    assert steps["push"]["status"] == "skipped"
    if outcome == "blocked":
        assert result["repair"]["terminal"] == "blocked"
        assert steps["run_agent"]["status"] == "skipped"
    elif outcome == "agent_failed":
        assert result["repair"]["ok"] is False
        assert steps["run_agent"]["status"] == "failed"
    else:
        assert steps["run_agent"]["returncode"] == 0
