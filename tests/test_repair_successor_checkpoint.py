"""Confirmed publication must not hide a later pre-checkpoint crash."""
import copy
import json
import sqlite3
from pathlib import Path

import pytest
from test_issue_triage_fala import base_effector, run_graph
from test_repair_publication_checkpoint import evidence, git, journal

from lokay.proc import pr_repair_checkpoint as checkpoint
from lokay.proc import pr_repair_receipts as receipts
from lokay.proc.reconcile_pr_repair_push import reconcile_pending


def confirmed_predecessor(tmp_path, monkeypatch):
    inputs, outputs, ref, target = evidence(tmp_path)
    config = tmp_path / 'config.yaml'
    config.write_text(
        f'state:\n  path: {tmp_path / "state.jsonl"}\n'
        'limits:\n  max_request_changes_per_pr: 2\n'
    )
    selected = {'ok': True, 'route': 'pr', 'repo': 'o/r', 'pr': 57,
                'branch': inputs['branch'], 'head_sha': target}
    remote = {'ok': True, 'route': 'open', 'state': 'OPEN', 'repo': 'o/r', 'pr': 57,
              'head_ref': inputs['branch'], 'head_ref_sha': target, 'head_repo': 'o/r'}
    monkeypatch.setattr('lokay.proc.probe_pr_state.probe', lambda **kw: remote)
    monkeypatch.setattr(
        'lokay.graph_run.pr_journal_dir',
        lambda path, repo, pr: Path(ref['db']).parent if (repo, pr) == ('o/r', 57) else None,
    )
    assert checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2)['route'] == 'checkpointed'
    first = receipts.read('o/r', 57, state_dir=tmp_path)['publication_checkpoint']
    intent = first['intent']
    assert receipts.prepare_push_intent(
        repo='o/r', pr=57, intent=intent, state_dir=tmp_path, budget=2,
    )['route'] == 'recorded'
    assert receipts.mark_push_attempted(
        repo='o/r', pr=57, intent_sha256=intent['intent_sha256'], state_dir=tmp_path,
    )['route'] == 'ready'
    assert reconcile_pending(config_path=str(config), live=True, selection=selected)['route'] == 'recovered'
    stored = receipts.read('o/r', 57, state_dir=tmp_path)
    assert stored['attempts'] == 1
    assert stored['checkpoint_terminal'] == 'confirmed_target'
    return inputs, outputs, ref, first, config, selected, remote


def successor_journal(tmp_path, inputs, outputs, ref, start):
    """A distinct tested B->C run; deliberately never call checkpoint.persist."""
    inputs, outputs = copy.deepcopy(inputs), copy.deepcopy(outputs)
    work = Path(outputs['worktree_add']['worktree'])
    (work / 'source').write_text('second repair')
    git(work, 'commit', '-am', 'second repair')
    target = git(work, 'rev-parse', 'HEAD')
    inputs.update(head_sha=start, reviewed_head_sha=start, review_result_sha256='d' * 64)
    inputs['review'].update(reviewed_head_sha=start, review_result_sha256='d' * 64)
    outputs['worktree_add'].update(repair_start_head_sha=start, worktree_head_sha=start)
    outputs['commit_initial_repair']['commit'] = target
    test = outputs['test_local']
    test.update(db=str(tmp_path / 'second-test.sqlite'), run_id='second-test-run')
    from lokay.proc._common import runner
    from lokay.test_cache import cache_key

    journal(Path(test['db']), 'test_local_execution', test['run_id'],
            {'repo': 'o/r', 'worktree': str(work)}, {
                'inspect_test_declaration': {'ok': True, 'route': 'test', 'worktree': str(work), 'test_argv': ['true']},
                'read_test_green_cache': {'ok': True, 'route': 'miss', 'key': cache_key(runner(), work, ('true',))},
                'run_declared_tests': {'ok': True, 'route': 'green', 'returncode': 0},
                'select_test_terminal': {'ok': True, 'result': test},
            })
    second_ref = {**ref, 'run_id': 'second-repair-run'}
    with sqlite3.connect(ref['db']) as conn:
        conn.execute('INSERT INTO runs VALUES (?, ?)', (second_ref['run_id'], 'pr_repair'))
        for name, value in outputs.items():
            job = 'pr_repair:' + name
            conn.execute('INSERT INTO processes VALUES (?, ?, ?, ?, ?)', (
                second_ref['run_id'], job, 'succeeded', json.dumps(inputs),
                json.dumps({'job': job, 'status': 'ok', 'payload': value}),
            ))
    return inputs, second_ref, target


def test_selected_pr_discovers_successor_after_confirmed_checkpoint(tmp_path, monkeypatch):
    inputs, outputs, ref, first, config, selected, remote = confirmed_predecessor(tmp_path, monkeypatch)
    second_inputs, second_ref, target = successor_journal(
        tmp_path, inputs, outputs, ref, first['intent']['target_head_sha'],
    )
    # Producer proof is valid, but no replacement checkpoint has been persisted.
    expected = checkpoint.derive(inputs=second_inputs, run_ref=second_ref)
    before = receipts.receipt_path('o/r', 57, state_dir=tmp_path).read_bytes()
    assert expected['intent']['target_head_sha'] == target
    observed = reconcile_pending(config_path=str(config), live=True, selection=selected)
    assert observed.get('recovery_case') == 'pre_attempt', observed
    stored = receipts.read('o/r', 57, state_dir=tmp_path)
    assert stored['publication_checkpoint'] == expected
    assert stored['checkpoint_history'][0]['checkpoint'] == first
    assert stored['checkpoint_history'][0]['terminal'] == 'confirmed_target'
    assert stored['attempts'] == 1
    assert stored.get('pending_push') is None
    assert 'checkpoint_terminal' not in stored
    assert receipts.receipt_path('o/r', 57, state_dir=tmp_path).read_bytes() != before

    # Exercise native selection/reconciliation/recovery conduction. Only external
    # observation and push effects are substituted; no GitHub or real push.
    marker = tmp_path / 'recovery-effect'
    body = base_effector(f'''
from lokay.organ.common import _conduction_values
from lokay.organ.pr_triage_department_boundary import handle_pr_triage_department
from lokay.proc import probe_pr_state, pr_repair_recovery
probe_pr_state.probe = lambda **kw: {remote!r}
pr_repair_recovery._mutation_gate = lambda *a: None
def push(**kw):
    Path({str(marker)!r}).write_text(a + ':' + kw['proof']['intent']['target_head_sha'])
    return {{'ok': True}}
pr_repair_recovery._push_exact = push
if a == 'list_pr_sieve': v.update(prs=[])
elif a == 'select_pr_sieve': v = {selected!r}
elif a == 'run_pr_sieve': raise AssertionError('must recover unpublished successor before review')
else: v = handle_pr_triage_department(a, {{'config_path': {str(config)!r}, 'live': True}}, _conduction_values(m), {{}})
''')
    result = run_graph(tmp_path, body, 'successor-recovery', 'pr_triage_department')
    assert result['ok'] is True, result
    assert marker.read_text() == 'recover_repair_pre_attempt:' + target
    stored = receipts.read('o/r', 57, state_dir=tmp_path)
    assert stored['attempts'] == 1
    assert stored['pending_push']['push_attempted'] is True
    assert stored['pending_push']['intent_sha256'] == expected['intent']['intent_sha256']
    assert stored['publication_checkpoint'] == expected
    assert stored['checkpoint_history'][0]['checkpoint'] == first

    for repo, pr in [('o/r', 99), ('other/repo', 57)]:
        unrelated = {**selected, 'repo': repo, 'pr': pr}
        assert reconcile_pending(config_path=str(config), live=True, selection=unrelated)['route'] == 'review'
    assert receipts.read('o/r', 57, state_dir=tmp_path) == stored
    for wrong in [{'head_ref_sha': 'e' * 40}, {'pr': 99}, {'repo': 'other/repo'}, {'head_ref': 'other'}]:
        identity = {**remote, 'head_ref_sha': target, **wrong}
        monkeypatch.setattr('lokay.proc.probe_pr_state.probe', lambda identity=identity, **kw: identity)
        assert reconcile_pending(config_path=str(config), live=True, selection=selected)['route'] == 'fail_closed'
        assert receipts.read('o/r', 57, state_dir=tmp_path)['attempts'] == 1
    remote['head_ref_sha'] = target
    monkeypatch.setattr('lokay.proc.probe_pr_state.probe', lambda **kw: remote)
    assert reconcile_pending(config_path=str(config), live=True, selection=selected)['route'] == 'recovered'
    assert receipts.read('o/r', 57, state_dir=tmp_path)['attempts'] == 2
    assert reconcile_pending(config_path=str(config), live=True, selection=selected)['route'] == 'review'
    final = receipts.read('o/r', 57, state_dir=tmp_path)
    assert final['attempts'] == 2
    assert final['checkpoint_history'][0]['checkpoint'] == first
    assert final['publication_checkpoint'] == expected
    assert final['checkpoint_terminal'] == 'confirmed_target'


def test_ambiguous_successor_runs_preserve_confirmed_predecessor(tmp_path, monkeypatch):
    inputs, outputs, ref, first, config, selected, _remote = confirmed_predecessor(tmp_path, monkeypatch)
    second_inputs, second_ref, _target = successor_journal(
        tmp_path, inputs, outputs, ref, first['intent']['target_head_sha'],
    )
    with sqlite3.connect(ref['db']) as conn:
        conn.execute('INSERT INTO runs VALUES (?, ?)', ('ambiguous-run', 'pr_repair'))
        conn.execute(
            'INSERT INTO processes SELECT ?, id, status, input_json, output_json '
            'FROM processes WHERE run_id=?', ('ambiguous-run', second_ref['run_id']),
        )
    # Both runs independently verify; neither may be chosen arbitrarily.
    for run_id in [second_ref['run_id'], 'ambiguous-run']:
        assert checkpoint.derive(inputs=second_inputs, run_ref={**ref, 'run_id': run_id})
    path = receipts.receipt_path('o/r', 57, state_dir=tmp_path)
    before = path.read_bytes()
    observed = reconcile_pending(config_path=str(config), live=True, selection=selected)
    assert observed['route'] == 'fail_closed', observed
    assert observed['reason'] == 'repair_legacy_lineage_unverified'
    assert path.read_bytes() == before
    assert receipts.read('o/r', 57, state_dir=tmp_path)['attempts'] == 1
    unrelated = {**selected, 'pr': 99}
    assert reconcile_pending(config_path=str(config), live=True, selection=unrelated)['route'] == 'review'


def test_successor_must_start_at_exact_confirmed_predecessor(tmp_path, monkeypatch):
    inputs, outputs, ref, first, config, selected, _remote = confirmed_predecessor(tmp_path, monkeypatch)
    second_inputs, second_ref, _target = successor_journal(
        tmp_path, inputs, outputs, ref, inputs['head_sha'],  # A, not confirmed B
    )
    assert checkpoint.derive(inputs=second_inputs, run_ref=second_ref)
    path = receipts.receipt_path('o/r', 57, state_dir=tmp_path)
    before = path.read_bytes()
    observed = reconcile_pending(config_path=str(config), live=True, selection=selected)
    assert observed['route'] == 'fail_closed', observed
    assert observed['reason'] == 'repair_checkpoint_conflict'
    assert path.read_bytes() == before
    assert receipts.read('o/r', 57, state_dir=tmp_path)['publication_checkpoint'] == first


@pytest.mark.parametrize('damage', ['repo', 'pr', 'branch', 'task', 'review', 'run', 'test', 'target'])
def test_invalid_successor_evidence_never_replaces_predecessor(tmp_path, monkeypatch, damage):
    inputs, outputs, ref, first, config, selected, _remote = confirmed_predecessor(tmp_path, monkeypatch)
    second_inputs, second_ref, _target = successor_journal(
        tmp_path, inputs, outputs, ref, first['intent']['target_head_sha'],
    )
    with sqlite3.connect(ref['db']) as conn:
        if damage == 'run':
            conn.execute('UPDATE runs SET correlation_path_id=? WHERE id=?', ('other', second_ref['run_id']))
        elif damage in {'test', 'target'}:
            name = 'test_local' if damage == 'test' else 'commit_initial_repair'
            conn.execute('UPDATE processes SET status=? WHERE run_id=? AND id=?',
                         ('failed', second_ref['run_id'], 'pr_repair:' + name))
        else:
            if damage in {'repo', 'pr', 'branch'}:
                second_inputs[damage] = 99 if damage == 'pr' else 'other/value'
            elif damage == 'task':
                second_inputs['task']['number'] = 99
            else:
                second_inputs['review']['review_result_sha256'] = 'f' * 64
            conn.execute('UPDATE processes SET input_json=? WHERE run_id=?',
                         (json.dumps(second_inputs), second_ref['run_id']))
    with pytest.raises((ValueError, KeyError)):
        checkpoint.derive(inputs=second_inputs, run_ref=second_ref)
    path = receipts.receipt_path('o/r', 57, state_dir=tmp_path)
    before = path.read_bytes()
    observed = reconcile_pending(config_path=str(config), live=True, selection=selected)
    assert observed.get('recovery_case') != 'pre_attempt'
    assert path.read_bytes() == before
    assert receipts.read('o/r', 57, state_dir=tmp_path)['publication_checkpoint'] == first


@pytest.mark.parametrize('terminal', ['confirmed_target', 'closed_merged'])
def test_terminal_checkpoint_without_successor_is_not_reactivated(tmp_path, monkeypatch, terminal):
    _inputs, _outputs, _ref, _first, config, selected, _remote = confirmed_predecessor(tmp_path, monkeypatch)
    if terminal == 'closed_merged':
        stored = receipts.read('o/r', 57, state_dir=tmp_path)
        stored['checkpoint_terminal'] = terminal
        receipts._write('o/r', 57, stored, state_dir=tmp_path)
    path = receipts.receipt_path('o/r', 57, state_dir=tmp_path)
    before = path.read_bytes()
    assert reconcile_pending(config_path=str(config), live=True, selection=selected)['route'] == 'review'
    assert path.read_bytes() == before
