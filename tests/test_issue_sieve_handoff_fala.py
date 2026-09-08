"""Native executor uses current sieve decisions, not label-only readiness."""

import json

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def test_native_executor_skips_parked_then_launches_unlabelled_ready(tmp_path):
    body = base_effector(
        """from unittest.mock import patch
from lokay.organ.common import _conduction_values
from lokay.organ.executor_department_boundary import handle_executor_department
from lokay.proc.select_next_issue import select as pick
from lokay.proc.select_issue_do_row import select as decide
from lokay.proc.summarize_issues import envelope
from lokay.sieve_decision import attach
pd = Path(%r)
up = _conduction_values(m)
rows = [{'repo': 'o/r', 'issue': n, 'labels': []} for n in (1, 2, 3)]
triage = {'decisions': [
    {'repo': 'o/r', 'issue': 1, 'route': 'skip', 'reason': 'host_ops'},
    {'repo': 'o/r', 'issue': 2, 'route': 'do', 'reason': 'ready'}]}
listed = attach({'ok': True, 'issues': rows}, triage)
inputs = {'pass_dir': str(pd), 'live': False}

def row(**kwargs):
    chosen = pick(kwargs['listed'], kwargs['last'], occupied=set())
    verdict = decide(chosen, kwargs['listed'])
    (pd / ('decision-' + str(kwargs['slot']))).write_text(json.dumps(verdict))
    # Deterministic launch receipt only; no harness is executed by this test.
    launch = {'route': 'started'} if verdict['route'] == 'do' else {}
    return envelope(chosen, verdict, launch)

if a == 'prepare_executor_rows':
    v.update(ok=True, budget=1, cap=1, spent=0, slot_count=8,
             listed=listed, last={}, pass_dir=str(pd), live=False)
else:
    with patch('lokay.proc.run_executor_row.run', side_effect=row):
        v.update(handle_executor_department(a, inputs, up, {}))
""" % str(tmp_path)
    )
    result = run_graph(tmp_path, body, 'sieve-to-executor', path_id='executor_rows')
    statuses = {k: v['status'] for k, v in result['effector_results'].items()}
    assert statuses['run_executor_row_3'] == 'skipped'
    first = json.loads((tmp_path / 'decision-1').read_text())
    second = json.loads((tmp_path / 'decision-2').read_text())
    assert (first['issue'], first['route'], first['reason']) == (1, 'skip', 'host_ops')
    assert (second['issue'], second['route']) == (2, 'do')
    assert json.loads((tmp_path / 'executor-rows.json').read_text())['spent'] == 1
