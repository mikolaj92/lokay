"""Native conduction must carry the serial cursor, not restart at row one."""

import json

import pytest
from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


@pytest.mark.parametrize("family,count", [("sieve", 5), ("executor", 8)])
def test_native_serial_children_receive_previous_cursor(tmp_path, family, count):
    # Only the child work is a deterministic fixture. Slot selection, cursor
    # classification, boundary dispatch and Fala conduction use production code.
    body = base_effector(
        """from unittest.mock import patch
from lokay.organ.common import _conduction_values
from lokay.organ.issue_triage_department_boundary import handle_issue_triage_department
from lokay.organ.executor_department_boundary import handle_executor_department
from lokay.proc.select_next_issue import select
family = %r
pd = Path(%r)
count = %r
sieve = family == 'sieve'
handler = handle_issue_triage_department if sieve else handle_executor_department
prepare_id = 'prepare_issue_sieve' if sieve else 'prepare_executor_rows'
module = 'lokay.proc.run_issue_sieve_row.run' if sieve else 'lokay.proc.run_executor_row.run'
issues = [{'repo': 'o/r', 'issue': n} for n in range(1, count + 2)]
inputs = {'listed': {'ok': True, 'issues': issues, 'count': len(issues), 'overflow': False},
          'last': {}, 'pass_dir': str(pd), 'live': False, 'budget': count}
up = _conduction_values(m)

def consume(**kwargs):
    picked = select(kwargs['listed'], kwargs['last'], occupied=set())
    remaining = picked['leftover_issues']
    (pd / ('picked-' + str(kwargs['slot']))).write_text(json.dumps(picked))
    # A terminal skip consumes this row; no coding worker is represented here.
    return {'ok': True, 'result': {'repo': picked['repo'], 'issue': picked['issue'],
            'route': 'skip', 'reason': 'closed', 'launched': None,
            'leftover': len(remaining), 'leftover_issues': remaining}}

if a == prepare_id:
    # Fixed input queue; no catalog, leases or external services in this test.
    v.update(ok=True, listed=inputs['listed'], last={}, budget=count, cap=count,
             spent=0, slot_count=count, pass_dir=str(pd), live=False)
else:
    with patch(module, side_effect=consume):
        result = handler(a, inputs, up, {})
    assert result is not None, a
    v.update(result)
""" % (family, str(tmp_path), count)
    )
    path_id = "issue_sieve_rows" if family == "sieve" else "executor_rows"
    result = run_graph(tmp_path, body, "cursor-" + family, path_id=path_id)
    failed = {k: v for k, v in result["effector_results"].items() if v["status"] == "failed"}
    assert not failed, failed
    picked = [json.loads((tmp_path / f"picked-{n}").read_text())["issue"] for n in range(1, count + 1)]
    assert picked == list(range(1, count + 1))
    if family == "sieve":
        cursor = json.loads((tmp_path / "issue-sieve.json").read_text())
        assert [row["issue"] for row in cursor["decisions"]] == picked


def test_native_executor_preserves_spent_budget_across_skip(tmp_path):
    body = base_effector(
        """from unittest.mock import patch
from lokay.organ.common import _conduction_values
from lokay.organ.executor_department_boundary import handle_executor_department
pd = Path(%r)
inputs = {'pass_dir': str(pd), 'live': False}
up = _conduction_values(m)

def row(**kwargs):
    slot = kwargs['slot']
    (pd / ('ran-' + str(slot))).write_text('visited')
    return {'ok': True, 'result': {'route': 'skip' if slot == 2 else 'do',
            'launched': None if slot == 2 else 'started',
            'leftover': 1, 'leftover_issues': [{'repo': 'o/r', 'issue': slot + 1}]}}

if a == 'prepare_executor_rows':
    v.update(ok=True, budget=2, cap=2, spent=0, pass_dir=str(pd), live=False)
else:
    with patch('lokay.proc.run_executor_row.run', side_effect=row):
        v.update(handle_executor_department(a, inputs, up, {}))
""" % str(tmp_path)
    )
    result = run_graph(tmp_path, body, 'cursor-budget', path_id='executor_rows')
    statuses = {k: v['status'] for k, v in result['effector_results'].items()}
    assert statuses['run_executor_row_3'] == 'succeeded'
    assert statuses['run_executor_row_4'] == 'skipped'
    cursor = json.loads((tmp_path / 'executor-rows.json').read_text())
    assert cursor['spent'] == 2


def test_executor_row_consumes_bound_skip_decision(tmp_path):
    # Nested department receipt carries decisions under ``result``. The row
    # must consume the bound skip so the next slot sees the next issue.
    body = base_effector(
        """from unittest.mock import patch
from lokay.organ.common import _conduction_values
from lokay.organ.executor_department_boundary import handle_executor_department
from lokay.proc.select_next_issue import select
pd = Path(%r)
count = %r
issues = [{"repo": "o/r", "issue": n, "labels": []} for n in range(1, count + 2)]
listed = {"ok": True, "issues": issues, "count": len(issues), "overflow": False}
decisions = [{"repo": "o/r", "issue": n, "route": "skip", "reason": "host_ops"}
             for n in range(1, count + 1)]
triage = {"ok": True, "department": "issue_triage", "result": {"decisions": decisions}}
inputs = {"listed": listed, "last": {}, "pass_dir": str(pd), "live": False,
          "budget": count, "triage": triage}
up = _conduction_values(m)

def consume(**kwargs):
    picked = select(kwargs["listed"], kwargs["last"], occupied=set())
    remaining = picked["leftover_issues"]
    (pd / ("picked-" + str(kwargs["slot"]))).write_text(json.dumps(picked))
    return {"ok": True, "result": {"repo": picked["repo"], "issue": picked["issue"],
            "route": "skip", "reason": "host_ops", "launched": None,
            "leftover": len(remaining), "leftover_issues": remaining}}

if a == "prepare_executor_rows":
    v.update(ok=True, route="run", listed=listed, last={}, budget=count, cap=count,
              spent=0, slot_count=count, pass_dir=str(pd), live=False,
              leftover=len(issues), leftover_issues=issues)
else:
    with patch("lokay.proc.run_executor_row.run", side_effect=consume):
        result = handle_executor_department(a, inputs, up, {})
    assert result is not None, a
    v.update(result)
""" % (str(tmp_path), 8)
    )
    result = run_graph(tmp_path, body, "nested-handoff", path_id="executor_rows")
    failed = {k: v for k, v in result["effector_results"].items() if v["status"] == "failed"}
    assert not failed, failed
    picked = [json.loads((tmp_path / f"picked-{n}").read_text())["issue"] for n in range(1, 9)]
    assert picked == list(range(1, 9))
