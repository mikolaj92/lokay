"""Recovery authority comes from durable Fala rows, not branch ancestry."""
import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from lokay.proc import pr_repair_receipts as receipts


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def journal(db, path, run, inputs, outputs):
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as conn:
        conn.executescript('''CREATE TABLE runs (id TEXT, correlation_path_id TEXT);
        CREATE TABLE processes (run_id TEXT, id TEXT, status TEXT, input_json TEXT, output_json TEXT);''')
        conn.execute('INSERT INTO runs VALUES (?, ?)', (run, path))
        for name, value in outputs.items():
            conn.execute('INSERT INTO processes VALUES (?, ?, ?, ?, ?)', (
                run, path + ':' + name, 'succeeded', json.dumps(inputs),
                json.dumps({'job': path + ':' + name, 'status': 'ok', 'payload': value}),
            ))


def evidence(tmp_path):
    work = tmp_path / 'work'
    work.mkdir()
    git(work, 'init', '-b', 'ai/fix/42')
    git(work, 'config', 'user.email', 'test@example.invalid')
    git(work, 'config', 'user.name', 'Test')
    git(work, 'remote', 'add', 'origin', 'https://github.com/o/r.git')
    (work / 'source').write_text('before')
    git(work, 'add', '.')
    git(work, 'commit', '-m', 'start')
    start = git(work, 'rev-parse', 'HEAD')
    git(work, 'update-ref', 'refs/remotes/origin/main', start)
    (work / 'source').write_text('after')
    git(work, 'commit', '-am', 'repair')
    target = git(work, 'rev-parse', 'HEAD')
    task = {'repo': 'o/r', 'type': 'Issue', 'state': 'OPEN', 'number': 42}
    inputs = {'repo': 'o/r', 'pr': 57, 'branch': 'ai/fix/42', 'head_sha': start,
                  'repair_kind': 'review', 'reviewed_head_sha': start, 'task': task,
                  'findings': [{'path': 'source', 'content': 'bug'}],
                  'task_identity_sha256': hashlib.sha256(receipts._canonical(task)).hexdigest(),
                  'review_result_sha256': 'c' * 64, 'live': True}
    inputs['review'] = {'verdict': 'request_changes', **{k: inputs[k] for k in (
        'task', 'findings', 'reviewed_head_sha', 'task_identity_sha256', 'review_result_sha256')}}
    db = tmp_path / 'repair' / 'state.sqlite'
    test_db = tmp_path / 'tests' / 'state.sqlite'
    from lokay.proc._common import runner
    from lokay.test_cache import cache_key
    key = cache_key(runner(), work, ('true',))
    test = {'ok': True, 'tested': True, 'skipped': False, 'tests': 'true', 'worktree': str(work),
                'repo': 'o/r', 'path_id': 'test_local_execution', 'db': str(test_db), 'run_id': 'test-run'}
    journal(test_db, 'test_local_execution', 'test-run', {'repo': 'o/r', 'worktree': str(work)}, {
        'inspect_test_declaration': {'ok': True, 'route': 'test', 'worktree': str(work), 'test_argv': ['true']},
        'read_test_green_cache': {'ok': True, 'route': 'miss', 'key': key},
        'run_declared_tests': {'ok': True, 'route': 'green', 'returncode': 0, 'tests': 'true'},
        'select_test_terminal': {'ok': True, 'result': test},
    })
    outputs = {
        'worktree_add': {'ok': True, 'route': 'ready', 'repo': 'o/r', 'pr': 57, 'branch': inputs['branch'],
                             'worktree': str(work), 'repair_start_head_sha': start, 'worktree_head_sha': start},
        'commit_initial_repair': {'ok': True, 'committed': True, 'commit': target, 'worktree': str(work)},
        'test_local': test,
        'finalize_repair_tests': {'ok': True, 'route': 'publish'},
        'assert_real_diff': {'ok': True, 'real': True},
    }
    journal(db, 'pr_repair', 'repair-run', inputs, outputs)
    return inputs, outputs, {'db': str(db), 'run_id': 'repair-run', 'path_id': 'pr_repair'}, target


@pytest.mark.parametrize('remote', ['unchanged', 'unavailable', 'closed'])
def test_native_checkpoint_consumer_routes_real_recovery_without_review(tmp_path, remote):
    from test_issue_triage_fala import base_effector, run_graph

    from lokay.proc import pr_repair_checkpoint as checkpoint
    inputs, _outputs, ref, target = evidence(tmp_path)
    assert checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2)['route'] == 'checkpointed'
    config = tmp_path / 'config.yaml'
    config.write_text(f'state:\n  path: {tmp_path / "state.jsonl"}\nlimits:\n  max_request_changes_per_pr: 2\n')
    marker = tmp_path / 'retried'
    identity = {'ok': True, 'route': 'open', 'state': 'OPEN', 'repo': 'o/r', 'pr': 57,
                'head_ref': inputs['branch'], 'head_ref_sha': inputs['head_sha'], 'head_repo': 'o/r'}
    if remote == 'unavailable': identity.update(route='unavailable', probe_failed=True)
    if remote == 'closed': identity.update(route='closed', state='CLOSED')
    body = base_effector(f'''
from lokay.organ.common import _conduction_values
from lokay.organ.pr_triage_department_boundary import handle_pr_triage_department
from lokay.proc import probe_pr_state, pr_repair_recovery
probe_pr_state.probe = lambda **kw: {identity!r}
pr_repair_recovery._mutation_gate = lambda *a: None
def push(**kw):
    Path({str(marker)!r}).write_text(kw['proof']['intent']['target_head_sha'])
    return {{'ok': True}}
pr_repair_recovery._push_exact = push
if a == 'list_pr_sieve': v.update(prs=[])
elif a == 'select_pr_sieve': v = {{'ok': True, 'route': 'pr', 'repo': 'o/r', 'pr': 57, 'branch': {inputs['branch']!r}, 'head_sha': {inputs['head_sha']!r}}}
elif a == 'run_pr_sieve': raise AssertionError('must not review unresolved publication')
else: v = handle_pr_triage_department(a, {{'config_path': {str(config)!r}, 'live': True}}, _conduction_values(m), {{}})
''')
    result = run_graph(tmp_path, body, 'checkpoint-' + remote, 'pr_triage_department')
    assert result['ok'] is True, result
    assert marker.exists() is (remote == 'unchanged'), result
    stored = receipts.read('o/r', 57, state_dir=tmp_path)
    assert stored['attempts'] == 0
    assert stored['publication_checkpoint']['intent']['target_head_sha'] == target
    if remote == 'unchanged': assert stored['pending_push']['push_attempted'] is True
    if remote == 'closed': assert stored['checkpoint_terminal'] == 'closed_merged'


def test_wrong_remote_pr_number_never_confirms_target(tmp_path, monkeypatch):
    from lokay.proc.pr_repair_push import reconcile_pending_push
    intent = receipts.build_push_intent(repo='o/r', pr=57, branch='ai/fix/42', repair_kind='ci', start_head_sha='a' * 40, target_head_sha='b' * 40)
    receipts.prepare_push_intent(repo='o/r', pr=57, intent=intent, state_dir=tmp_path)
    receipts.mark_push_attempted(repo='o/r', pr=57, intent_sha256=intent['intent_sha256'], state_dir=tmp_path)
    monkeypatch.setattr('lokay.proc.probe_pr_state.probe', lambda **kw: {
        'ok': True, 'pr': 99, 'repo': 'o/r', 'route': 'open', 'state': 'OPEN',
        'head_ref': 'ai/fix/42', 'head_ref_sha': 'b' * 40, 'head_repo': 'o/r'})
    result = reconcile_pending_push(repo='o/r', pr=57, config_path=None, live=True, state_dir=tmp_path)
    assert result['route'] == 'fail_closed', result
    assert receipts.read('o/r', 57, state_dir=tmp_path)['attempts'] == 0


def test_checkpoint_retains_bounded_evidence_not_agent_transcripts(tmp_path):
    from lokay.proc import pr_repair_checkpoint as checkpoint
    inputs, _outputs, ref, _target = evidence(tmp_path)
    with sqlite3.connect(ref['db']) as conn:
        conn.execute('INSERT INTO processes VALUES (?, ?, ?, ?, ?)', (
            ref['run_id'], 'pr_repair:run_agent', 'succeeded', json.dumps(inputs),
            json.dumps({'job': 'pr_repair:run_agent', 'status': 'ok', 'payload': {'ok': True, 'stdout': 'x' * 2_000_000}})))
    assert checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2)['route'] == 'checkpointed'
    assert receipts.receipt_path('o/r', 57, state_dir=tmp_path).stat().st_size < 100_000


def test_new_repair_checkpoint_archives_confirmed_predecessor(tmp_path):
    from lokay.proc import pr_repair_checkpoint as checkpoint
    inputs, _outputs, ref, target = evidence(tmp_path)
    checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2)
    stored = receipts.read('o/r', 57, state_dir=tmp_path)
    first = stored['publication_checkpoint']
    stored['checkpoint_terminal'] = 'confirmed_target'
    stored['attempts'] = 1
    stored['last_head_sha'] = target
    receipts._write('o/r', 57, stored, state_dir=tmp_path)
    import copy
    second = copy.deepcopy(first)
    second['intent'] = receipts.build_push_intent(repo='o/r', pr=57, branch='ai/fix/42', repair_kind='ci', start_head_sha=target, target_head_sha='d' * 40)
    second['sha256'] = hashlib.sha256(receipts._canonical({k:v for k,v in second.items() if k != 'sha256'})).hexdigest()
    result = receipts.record_publication_checkpoint(proof=second, state_dir=tmp_path, budget=2)
    assert result['route'] == 'checkpointed', result
    stored = receipts.read('o/r', 57, state_dir=tmp_path)
    assert stored['checkpoint_history'][0]['checkpoint'] == first
    assert 'checkpoint_terminal' not in stored


def test_push_cannot_replace_checkpoint_with_an_unrelated_new_head(tmp_path, monkeypatch):
    from lokay.proc import pr_repair_checkpoint as checkpoint
    from lokay.proc.pr_repair_push import prepare_live_push
    inputs, outputs, ref, _target = evidence(tmp_path)
    checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2)
    work = Path(outputs['worktree_add']['worktree'])
    (work / 'source').write_text('later commit')
    git(work, 'commit', '-am', 'unrelated')
    config = tmp_path / 'config.yaml'
    config.write_text(f'mode: live\nstate:\n  path: {tmp_path / "state.jsonl"}\nlimits:\n  max_request_changes_per_pr: 2\n')
    monkeypatch.setattr('lokay.preflight.require_healthy', lambda *a, **kw: None)
    result = prepare_live_push(config_path=str(config), repo='o/r', pr=57, branch=inputs['branch'],
                              worktree=work, start_head_sha=inputs['head_sha'], repair_kind='review',
                              **{k: inputs[k] for k in ('reviewed_head_sha', 'task', 'findings', 'task_identity_sha256', 'review_result_sha256')})
    assert result['route'] == 'fail_closed', result
    assert receipts.read('o/r', 57, state_dir=tmp_path).get('pending_push') is None


def test_failed_retry_retains_intent_without_spending_budget(tmp_path, monkeypatch):
    from lokay.proc import pr_repair_checkpoint as checkpoint
    from lokay.proc import pr_repair_recovery as recovery
    inputs, _outputs, ref, target = evidence(tmp_path)
    checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2)
    monkeypatch.setattr(recovery, '_mutation_gate', lambda *a: None)
    monkeypatch.setattr(recovery, '_push_exact', lambda **kw: {'ok': False, 'reason': 'push_failed'})
    monkeypatch.setattr('lokay.proc.probe_pr_state.probe', lambda **kw: {
        'ok': True, 'route': 'open', 'state': 'OPEN', 'head_ref': inputs['branch'],
        'head_ref_sha': inputs['head_sha'], 'head_repo': 'o/r'})
    for _ in range(2):
        result = recovery.retry(repo='o/r', pr=57, config_path=None, state_dir=tmp_path)
        assert result['reason'] == 'push_failed'
        stored = receipts.read('o/r', 57, state_dir=tmp_path)
        assert stored['attempts'] == 0
        assert stored['pending_push']['target_head_sha'] == target
        assert stored['pending_push']['push_attempted'] is True


def test_retry_refuses_a_different_push_destination(tmp_path):
    from lokay.proc import pr_repair_checkpoint as checkpoint
    inputs, outputs, ref, _target = evidence(tmp_path)
    checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2)
    git(Path(outputs['worktree_add']['worktree']), 'remote', 'set-url', '--push', 'origin', 'https://github.com/other/repo.git')
    proof = receipts.read('o/r', 57, state_dir=tmp_path)['publication_checkpoint']
    with pytest.raises(ValueError, match='repository'):
        checkpoint.verify_local(proof)


def test_review_digest_must_match_durable_review_handoff(tmp_path):
    from lokay.proc import pr_repair_checkpoint as checkpoint
    inputs, _outputs, ref, _target = evidence(tmp_path)
    inputs['review']['review_result_sha256'] = 'f' * 64
    with sqlite3.connect(ref['db']) as conn:
        conn.execute('UPDATE processes SET input_json=?', (json.dumps(inputs),))
    assert checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2)['route'] == 'fail_closed'


def test_cross_run_test_input_is_not_accepted(tmp_path):
    from lokay.proc import pr_repair_checkpoint as checkpoint
    inputs, _outputs, ref, _target = evidence(tmp_path)
    with sqlite3.connect(ref['db']) as conn:
        altered = {**inputs, 'head_sha': 'f' * 40}
        conn.execute("UPDATE processes SET input_json=? WHERE id='pr_repair:test_local'", (json.dumps(altered),))
    assert checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2)['route'] == 'fail_closed'


def test_journal_review_handoff_must_match_authorized_task_and_start(tmp_path):
    from lokay.proc import pr_repair_checkpoint as checkpoint
    inputs, _outputs, ref, _target = evidence(tmp_path)
    inputs['task']['repo'] = 'foreign/repo'
    inputs['task_identity_sha256'] = hashlib.sha256(receipts._canonical(inputs['task'])).hexdigest()
    with sqlite3.connect(ref['db']) as conn:
        conn.execute('UPDATE processes SET input_json=?', (json.dumps(inputs),))
    assert checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2)['route'] == 'fail_closed'


def test_corrupt_checkpoint_is_not_retry_authority(tmp_path):
    from lokay.proc import pr_repair_checkpoint as checkpoint
    inputs, _outputs, ref, _target = evidence(tmp_path)
    checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2)
    path = receipts.receipt_path('o/r', 57, state_dir=tmp_path)
    stored = json.loads(path.read_text())
    stored['publication_checkpoint']['task']['number'] = 99
    path.write_text(json.dumps(stored))
    with pytest.raises(ValueError):
        receipts.read('o/r', 57, state_dir=tmp_path)


def test_checkpoint_precedes_push_preflight_and_preserves_full_lineage(tmp_path):
    inputs, _outputs, ref, target = evidence(tmp_path)
    from lokay.proc import pr_repair_checkpoint as checkpoint
    result = checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2)
    assert result['route'] == 'checkpointed', result
    stored = receipts.read('o/r', 57, state_dir=tmp_path)
    proof = stored['publication_checkpoint']
    assert proof['intent']['target_head_sha'] == target
    assert proof['intent']['start_head_sha'] == inputs['head_sha']
    assert proof['run'] == ref
    assert proof['task'] == inputs['task']
    assert proof['test']['run_id'] == 'test-run'
    assert stored['attempts'] == 0
    assert stored.get('pending_push') is None
    assert checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2) == result


@pytest.mark.parametrize('state', ['CLOSED', 'MERGED'])
def test_closed_remote_archives_intent_without_counting(tmp_path, monkeypatch, state):
    from lokay.proc import pr_repair_checkpoint as checkpoint
    from lokay.proc.pr_repair_recovery import close_pending
    inputs, _outputs, ref, _target = evidence(tmp_path)
    checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2)
    intent = receipts.read('o/r', 57, state_dir=tmp_path)['publication_checkpoint']['intent']
    receipts.prepare_push_intent(repo='o/r', pr=57, intent=intent, state_dir=tmp_path, budget=2)
    monkeypatch.setattr(receipts, 'resolve_state_dir', lambda cfg: tmp_path)
    monkeypatch.setattr('lokay.proc.probe_pr_state.probe', lambda **kw: {
        'ok': True, 'route': state.lower(), 'state': state, 'head_ref': inputs['branch'],
        'head_ref_sha': inputs['head_sha'], 'head_repo': 'o/r'})
    observed = {'repo': 'o/r', 'pr': 57, 'recovery_case': 'closed_merged'}
    result = close_pending(observed=observed, config_path=None)
    assert result['route'] == 'recovered', result
    stored = receipts.read('o/r', 57, state_dir=tmp_path)
    assert stored['attempts'] == 0
    assert stored['pending_push'] is None
    assert stored['closed_push']['intent_sha256'] == intent['intent_sha256']
    assert stored['publication_checkpoint']['intent'] == intent
    assert stored['checkpoint_terminal'] == 'closed_merged'


def test_legacy_committed_before_intent_recovered_from_durable_journal(tmp_path, monkeypatch):
    from lokay.proc import pr_repair_checkpoint as checkpoint
    inputs, _outputs, ref, target = evidence(tmp_path)
    monkeypatch.setattr('lokay.graph_run.pr_journal_dir', lambda *a, **kw: Path(ref['db']).parent)
    result = checkpoint.recover_legacy(repo='o/r', pr=57, branch=inputs['branch'], state_dir=tmp_path, budget=2)
    assert result['route'] == 'checkpointed', result
    assert receipts.read('o/r', 57, state_dir=tmp_path)['publication_checkpoint']['intent']['target_head_sha'] == target


@pytest.mark.parametrize('attempted', [False, True])
def test_unchanged_remote_retries_only_verified_checkpoint(tmp_path, monkeypatch, attempted):
    from lokay.proc import pr_repair_checkpoint as checkpoint
    from lokay.proc import pr_repair_recovery as recovery
    from lokay.proc.pr_repair_push import reconcile_pending_push
    inputs, _outputs, ref, target = evidence(tmp_path)
    assert checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2)['route'] == 'checkpointed'
    proof = receipts.read('o/r', 57, state_dir=tmp_path)['publication_checkpoint']
    intent = proof['intent']
    receipts.prepare_push_intent(repo='o/r', pr=57, intent=intent, budget=2, state_dir=tmp_path)
    if attempted:
        receipts.mark_push_attempted(repo='o/r', pr=57, intent_sha256=intent['intent_sha256'], state_dir=tmp_path)
    monkeypatch.setattr('lokay.proc.probe_pr_state.probe', lambda **kw: {
        'ok': True, 'route': 'open', 'state': 'OPEN', 'head_ref': inputs['branch'],
        'head_ref_sha': inputs['head_sha'], 'head_repo': 'o/r'})
    observed = reconcile_pending_push(repo='o/r', pr=57, config_path=None, live=True, state_dir=tmp_path)
    assert observed['recovery_case'] == ('remote_unchanged' if attempted else 'pre_attempt')
    calls = []
    def push(**kwargs):
        calls.append(kwargs)
        pending = receipts._read_unlocked('o/r', 57, state_dir=tmp_path)['pending_push']
        assert pending['push_attempted'] is True
        return {'ok': True, 'head_sha': target}
    monkeypatch.setattr(recovery, '_push_exact', push)
    monkeypatch.setattr(recovery, '_mutation_gate', lambda *args: None)
    result = recovery.retry(repo='o/r', pr=57, config_path=None, state_dir=tmp_path)
    assert result['route'] == 'retry_pending', result
    assert len(calls) == 1
    assert receipts.read('o/r', 57, state_dir=tmp_path)['attempts'] == 0
    monkeypatch.setattr('lokay.proc.probe_pr_state.probe', lambda **kw: {
        'ok': True, 'route': 'open', 'state': 'OPEN', 'head_ref': inputs['branch'],
        'head_ref_sha': target, 'head_repo': 'o/r'})
    assert reconcile_pending_push(repo='o/r', pr=57, config_path=None, live=True, state_dir=tmp_path)['route'] == 'confirmed'
    assert receipts.read('o/r', 57, state_dir=tmp_path)['attempts'] == 1
    assert recovery.retry(repo='o/r', pr=57, config_path=None, state_dir=tmp_path)['route'] != 'retry_pending'
    assert len(calls) == 1


def test_authored_checkpoint_survives_failed_publication_preflight(tmp_path):
    import os
    import sys
    import tomllib

    from test_issue_triage_fala import base_effector

    from lokay.graph_run import _materialize_package

    inputs, outputs, ref, target = evidence(tmp_path)
    root = Path(__file__).resolve().parents[1]
    db = tmp_path / 'native.sqlite'
    ref = {'db': str(db), 'run_id': 'native-repair', 'path_id': 'pr_repair'}
    inputs['repair_run_ref'] = ref
    config = tmp_path / 'config.yaml'
    config.write_text(f'state:\n  path: {tmp_path / "state.jsonl"}\nlimits:\n  max_request_changes_per_pr: 2\n')
    inputs['config_path'] = str(config)
    fixture = tmp_path / 'fixture.py'
    fixture.write_text(base_effector(f'''
from fala import sdk
from lokay.organ.common import _conduction_values
from lokay.organ.repair_boundary import handle_repair_boundary
values = {outputs!r}
node = m.job.split(':')[-1]
if node == 'checkpoint_repair_publication':
    v = handle_repair_boundary(a, dict(sdk.declared_inputs(m)), _conduction_values(m), {{'repo': 'o/r', 'pr_number': 57}})
elif node == 'push':
    raise RuntimeError('simulated push preflight rejection')
elif node in values: v = values[node]
elif node == 'localize': v.update(route='ready')
elif node in ('finalize_repair_result', 'select_initial_repair'): v.update(route='repaired')
elif node == 'select_repair_test': v.update(route='pass')
'''))
    package = _materialize_package(root / 'fala/lokay.fala-package.toml', tmp_path / 'pkg.toml', project=root, path_id='pr_repair')
    nodes = tomllib.loads(package.read_text())['correlation_paths'][0]['effectors']
    commands = {n['id']: [sys.executable, str(fixture)] for n in nodes}
    script = '''import fala,json,sys
print(json.dumps(fala.host_run_package(db_path=sys.argv[1],package_path=sys.argv[2],path_id='pr_repair',run_id='native-repair',inputs=json.loads(sys.argv[3]),command_overrides=json.loads(sys.argv[4]),max_ticks=64)))'''
    env = os.environ.copy()
    for k in ('DYLD_LIBRARY_PATH', 'DYLD_FALLBACK_LIBRARY_PATH'): env.pop(k, None)
    for k in ('LOKAY_ROOT', 'LOKAY_PROCESS_HEAD', 'LOKAY_HOST_FF_FETCHED', 'LOKAY_HEALTH_LEASE', 'LOKAY_HEALTH_LEASE_PATH', 'LOKAY_DISABLE_HEALTH_LEASE_ISSUE', 'PYTHONPATH', 'OCR_LLM_API_KEY'): env.setdefault(k, '')
    run = subprocess.run([sys.executable, '-c', script, str(db), str(package), json.dumps(inputs), json.dumps(commands)], env=env, capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout.splitlines()[-1])
    stored = receipts.read('o/r', 57, state_dir=tmp_path)
    assert stored.get('publication_checkpoint'), result
    assert stored['publication_checkpoint']['intent']['target_head_sha'] == target
    assert stored['publication_checkpoint']['run'] == ref
    assert not stored.get('pending_push')


def test_checkpoint_is_durable_even_when_later_dirt_preflight_refuses(tmp_path):
    from lokay.proc import pr_repair_checkpoint as checkpoint
    inputs, outputs, ref, _target = evidence(tmp_path)
    Path(outputs['worktree_add']['worktree'], 'unrelated').write_text('preserve me')
    result = checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2)
    assert result['route'] == 'checkpointed', result
    proof = receipts.read('o/r', 57, state_dir=tmp_path)['publication_checkpoint']
    with pytest.raises(ValueError, match='dirty'):
        checkpoint.verify_local(proof)
    assert Path(outputs['worktree_add']['worktree'], 'unrelated').read_text() == 'preserve me'


@pytest.mark.parametrize('damage', ['commit', 'task', 'test', 'branch', 'repo', 'run', 'test_key'])
def test_checkpoint_never_trusts_a_descendant_without_exact_evidence(tmp_path, damage):
    inputs, outputs, ref, _target = evidence(tmp_path)
    from lokay.proc import pr_repair_checkpoint as checkpoint
    if damage == 'commit':
        work = Path(outputs['worktree_add']['worktree'])
        (work / 'source').write_text('unrelated descendant')
        git(work, 'commit', '-am', 'unrelated')
    elif damage == 'run':
        ref['run_id'] = 'other-run'
    elif damage == 'test_key':
        with sqlite3.connect(outputs['test_local']['db']) as conn:
            conn.execute("UPDATE processes SET output_json=? WHERE id LIKE '%read_test_green_cache'", (json.dumps({'job': 'test_local_execution:read_test_green_cache', 'status': 'ok', 'payload': {'ok': True, 'route': 'miss', 'key': None}}),))
    elif damage == 'test':
        with sqlite3.connect(outputs['test_local']['db']) as conn:
            conn.execute("UPDATE processes SET status='failed' WHERE id LIKE '%run_declared_tests'")
    else:
        inputs[damage] = {'number': 99} if damage == 'task' else 'foreign/value'
    result = checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2)
    assert result['route'] == 'fail_closed', result
    assert not receipts.read('o/r', 57, state_dir=tmp_path).get('publication_checkpoint')
