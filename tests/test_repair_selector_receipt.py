"""Native selector -> skipped child -> real factory receipt (#1163)."""

import json
from pathlib import Path

import pytest
from test_issue_triage_fala import base_effector, run_graph

from lokay.graph_run import normalize_path_result
from lokay.pass_history import read_pass_history
from lokay.pass_receipt import read_pass_receipt
from lokay.proc import pr_repair_receipts


@pytest.mark.parametrize("case, reason", [
    ("budget", "pr_repair_budget_exhausted"),
    ("handoff", "ci_repair_contains_review_handoff"),
    ("receipt", "pr_repair_receipt_invalid"),
    ("review_handoff", "review_repair_handoff_incomplete"),
    ("kind", "repair_kind_invalid"),
    ("executed", "repair_start_head_mismatch"),
    ("published", "repair_pushed"),
    ("disabled", ""),
    ("no_verdict", ""),
])
def test_native_repair_authorization_reaches_receipt(tmp_path, case, reason):
    target = {"repo": "o/r", "pr": 9, "branch": "ai/fix/42-task"}
    head = "a" * 40
    triage = {
        "ok": True, **target, "head_sha": head, "repair_start_head_sha": head,
        "verdict": "repair", "repair_kind": "ci",
        "triage": {"repairable": True, "repair_kind": "ci"},
        "leftover_prs": [{**target, "head_sha": head}],
    }
    if case == "handoff":
        triage["reviewed_head_sha"] = head
    if case in {"review_handoff", "kind"}:
        kind = "review" if case == "review_handoff" else "unknown"
        triage.update(repair_kind=kind, triage={"repairable": True, "repair_kind": kind})
    if case == "no_verdict":
        triage.update(verdict="wait", triage={"repairable": False})
    if case == "budget":
        pr_repair_receipts.stamp("o/r", 9, state_dir=tmp_path, budget=1)
    if case == "receipt":
        path = pr_repair_receipts.receipt_path("o/r", 9, state_dir=tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{broken")
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*.json")}
    child = {
        "ok": True, "route": "fail_closed", "reason": reason,
        **target, "repair_start_head_sha": head,
        "repair": {"ok": False, "terminal": "blocked", "head_sha": head},
    }
    if case == "published":
        child.update(route="completed", repair={
            "ok": True, "terminal": "publish", "published": True,
            "repaired": True, "head_sha": "b" * 40,
        })
    body = base_effector(f'''
from lokay.organ.common import _conduction_values
from lokay.organ.factory import handle_factory
from lokay.proc.select_pr_repair_department import select
up = _conduction_values(m)
if a == 'factory_begin_host_gate': v.update(route='begin')
if a == 'factory_begin': v.update(state_path={str(tmp_path / 'state.jsonl')!r})
if a in {{'select_self_repair_department', 'select_issue_triage_department', 'select_executor_department'}}: v.update(route='skip')
if a == 'select_pr_triage_department': v.update(route='run')
if a == 'run_pr_triage_department': v = {triage!r}
if a == 'select_pr_repair_department':
    v = select(up['run_pr_triage_department'], enabled={case != 'disabled'!r},
               triage_ran=True, state_dir=Path({str(tmp_path)!r}), budget=1)
    Path({str(tmp_path / 'selector.json')!r}).write_text(json.dumps(v))
if a == 'run_pr_repair_department': v = {child!r}
if a in {{'record_pass', 'factory_pass_terminal'}}:
    if a == 'record_pass':
        Path({str(tmp_path / 'conduction.json')!r}).write_text(json.dumps(up))
    v = handle_factory(a, {{}}, up, {{
        'cfg': [], 'live': [], 'repo': 'local/factory', 'issue_number': None,
        'pr_number': None, 'repair_mode': False, 'branch': None,
    }})
''')
    native = run_graph(tmp_path, body, f"selector-{case}", path_id="factory_pass")
    assert native["run_status"] == "completed"
    nodes = native["effector_results"]
    executed = case in {"executed", "published"}
    assert nodes["run_pr_repair_department"]["status"] == (
        "succeeded" if executed else "skipped"
    )
    assert nodes["record_pass"]["status"] == "succeeded"
    selected = json.loads((tmp_path / "selector.json").read_text())
    conducted = json.loads((tmp_path / "conduction.json").read_text())
    assert conducted["select_pr_repair_department"] == selected
    if reason and not executed:
        assert selected["route"] == "fail_closed"
        assert selected["reason"] == reason
    result = normalize_path_result({"ok": True, "path_id": "factory_pass", "fala": native})
    receipt = read_pass_receipt(state_path=tmp_path / "state.jsonl")
    assert receipt is not None
    history = read_pass_history(state_path=tmp_path / "state.jsonl")
    for value in (result, receipt, history[-1]):
        blocked = bool(reason) and case != "published"
        assert value["ok"] is (not blocked)
        assert value["health"] == (
            "pr_repair_blocked" if blocked else "repairing" if case == "published" else "waiting"
        )
        assert value["outcome"] == "none"
        assert value["idle"] is False
        assert value["remaining"]["leftover_prs"] == triage["leftover_prs"]
        if reason:
            evidence = value["pr_repair"]
            assert {key: evidence[key] for key in target} == target
            assert evidence["reason"] == reason
            assert evidence["repair_start_head_sha"] == head
            assert value["lane"] == "product"
            if blocked:
                assert value["reason"] == reason
            else:
                assert evidence["head_sha"] == "b" * 40
                assert value["progress"] == 1
    # Recording must not spend budget or modify the selector's durable receipt.
    for path, content in before.items():
        assert Path(path).read_bytes() == content
