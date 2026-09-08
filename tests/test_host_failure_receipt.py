"""Host sync failures stop departments and persist an unhealthy receipt."""

import json
import subprocess
import sys

import pytest
from test_host_ff import _pair, _git
from lokay.proc.gate_factory_begin_host import gate
from lokay.organ.departments_boundary import handle_departments
from lokay.organ.factory import handle_factory


@pytest.mark.parametrize('host', [{}, {'ok': False, 'reason': 'host_behind'}, {'updated': False}])
def test_missing_or_failed_live_sync_never_begins(host):
    result = gate(host, live=True, checkout='')
    assert result['route'] == 'blocked'
    assert result['health'] == 'host_behind'


@pytest.mark.parametrize('atom', ['select_self_repair_department', 'select_issue_triage_department',
                                  'select_executor_department', 'select_pr_triage_department',
                                  'select_pr_repair_department'])
def test_departments_skip_host_failure(atom):
    result = handle_departments(atom, {'live': True},
                                {'factory_begin_host_gate': {'route': 'blocked', 'health': 'host_behind',
                                                             'reason': 'host_behind'}}, {})
    assert result['route'] == 'skip'
    assert result['reason'] == 'host_behind'


def test_real_nonancestor_cli_failure_reaches_persisted_receipt(tmp_path):
    _, host = _pair(tmp_path)
    (host / 'local.txt').write_text('unpublished work')
    _git(host, 'add', 'local.txt')
    _git(host, 'commit', '-m', 'local unpublished change')
    run = subprocess.run([sys.executable, '-m', 'lokay.proc.host_ff', '--live', '--checkout', str(host)],
                         text=True, capture_output=True)
    assert run.returncode != 0
    failed = json.loads(run.stdout.strip().splitlines()[-1])
    assert failed['ok'] is False
    assert 'not an ancestor' in failed['error']
    stopped = gate(failed, live=True, checkout=str(host))
    assert stopped['route'] == 'blocked'
    out = handle_factory('record_pass', {'live': True},
                         {'factory_begin_host_gate': stopped,
                          'factory_begin': {'state_path': str(tmp_path / 'state.jsonl'), 'live': True}},
                         {'cfg': [], 'live': [], 'repo': '', 'issue_number': None,
                          'pr_number': None, 'repair_mode': False, 'branch': ''})
    receipt = json.loads((tmp_path / 'last-pass.json').read_text())
    assert receipt['ok'] is False
    assert receipt['health'] == 'host_behind'
    assert receipt['reason'] == 'host_behind'
    assert receipt['progress'] == 0
    assert receipt['idle'] is False
    assert out['result']['ok'] is False
    assert out['result']['health'] == receipt['health']
    assert (host / 'local.txt').read_text() == 'unpublished work'


def test_native_failed_host_stops_factory_and_records_failure(tmp_path):
    from test_implementation_selection_fala import run_graph
    from test_issue_triage_fala import base_effector
    _, host = _pair(tmp_path)
    (host / 'unpublished.txt').write_text('keep me')
    _git(host, 'add', 'unpublished.txt')
    _git(host, 'commit', '-m', 'unpublished')
    body = base_effector(
        """import subprocess, sys
from lokay.organ.common import _conduction_values
from lokay.proc.gate_factory_begin_host import gate
from lokay.organ.departments_boundary import handle_departments
from lokay.proc.record_pass import record
up = _conduction_values(m)
if a == 'host_ff':
    run = subprocess.run([sys.executable, '-m', 'lokay.proc.host_ff', '--live', '--checkout', %r], text=True, capture_output=True)
    assert run.returncode != 0
    v.update(json.loads(run.stdout.strip().splitlines()[-1]))
elif a == 'factory_begin_host_gate':
    v.update(gate(up.get('host_ff') or {}, live=True, checkout=''))
elif a.startswith('select_') and a.endswith('_department'):
    v.update(handle_departments(a, {'live': True}, up, {}))
elif a == 'record_pass':
    v.update(record(begin={'state_path': %r, 'live': True}, host_gate=up['factory_begin_host_gate']))
elif a == 'factory_begin' or (a.startswith('run_') and a.endswith('_department')):
    raise AssertionError('Host failure must prevent workspace and departments: ' + a)
""" % (str(host), str(tmp_path / 'state.jsonl'))
    )
    # Preserve the actual unsuccessful atom status as well as its JSON envelope.
    body += "\nif a == 'host_ff': raise SystemExit(1)\n"
    result = run_graph(tmp_path, body, 'host-failed', path_id='factory_pass')
    statuses = {k: v['status'] for k, v in result['effector_results'].items()}
    assert statuses['host_ff'] == 'failed'
    assert statuses['factory_begin'] == 'skipped'
    for name in ('self_repair', 'issue_triage', 'executor', 'pr_triage', 'pr_repair'):
        assert statuses['run_' + name + '_department'] == 'skipped'
    assert statuses['record_pass'] == 'succeeded'
    receipt = json.loads((tmp_path / 'last-pass.json').read_text())
    assert receipt['ok'] is False
    assert receipt['health'] == 'host_behind'
    assert receipt['progress'] == 0
    assert (host / 'unpublished.txt').read_text() == 'keep me'


@pytest.mark.parametrize('route,health', [('restart', 'host_updated'), ('blocked', 'host_behind')])
def test_stopped_host_metadata_reaches_top_level_receipt(tmp_path, route, health):
    from lokay.proc.record_pass import record
    out = record(begin={'state_path': str(tmp_path / 'state.jsonl')},
                 host_gate={'route': route, 'reason': health})
    assert out['health'] == health
    assert out['reason'] == health
    assert out['restart_required'] is (route == 'restart')
    assert out['result']['health'] == health
