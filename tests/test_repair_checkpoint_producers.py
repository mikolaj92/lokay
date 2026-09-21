"""Real publication/test producers must cross the durable checkpoint boundary."""
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from test_repair_publication_checkpoint import evidence, git

from lokay.proc import pr_repair_checkpoint as checkpoint


def insert_output(ref, inputs, name, value):
    with sqlite3.connect(ref['db']) as conn:
        conn.execute('DELETE FROM processes WHERE run_id=? AND id=?',
                     (ref['run_id'], ref['path_id'] + ':' + name))
        conn.execute('INSERT INTO processes VALUES (?, ?, ?, ?, ?)', (
            ref['run_id'], ref['path_id'] + ':' + name, 'succeeded', json.dumps(inputs),
            json.dumps({'job': ref['path_id'] + ':' + name, 'status': 'ok', 'payload': value})))


def replace_output(ref, name, value):
    with sqlite3.connect(ref['db']) as conn:
        conn.execute('UPDATE processes SET output_json=? WHERE run_id=? AND id=?', (
            json.dumps({'job': ref['path_id'] + ':' + name, 'status': 'ok', 'payload': value}),
            ref['run_id'], ref['path_id'] + ':' + name))


def real_tests(tmp_path, monkeypatch, inputs, work, *, scoped):
    from lokay.graph_run import run_path
    from lokay.proc import test_local_execution_subflow as subflow

    (work / 'src').mkdir()
    (work / 'tests').mkdir()
    (work / 'src' / 'widget.py').write_text('value = 1\n')
    (work / 'tests' / 'test_widget.py').write_text('def test_widget(): assert True\n')
    (work / 'tests' / 'test_other.py').write_text(
        'def test_other(): assert ' + ('False' if scoped else 'True') + '\n')
    (work / 'pyproject.toml').write_text('[tool.lokay]\ntest = ' + json.dumps([
        sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider']) + '\n')
    (work / '.gitignore').write_text('__pycache__/\n')
    git(work, 'add', '.')
    git(work, 'commit', '-m', 'test baseline')
    git(work, 'update-ref', 'refs/remotes/origin/main', 'HEAD')
    (work / 'src' / 'widget.py').write_text('value = 2\n')
    git(work, 'commit', '-am', 'tested repair')
    monkeypatch.setattr(subflow, 'run_path', lambda **kw: run_path(
        **kw, db_path=tmp_path / 'native-tests'))
    result = subflow.run(worktree=str(work), changed_scope=scoped, repo=inputs['repo'], issue=42)
    assert result['ok'] is True and result['tested'] is True, json.dumps(result, indent=2)
    assert result['scoped'] is scoped
    return result


def bind_tests(ref, outputs, test, *, recheck=False):
    commit = dict(outputs['commit_initial_repair'])
    commit['commit'] = git(Path(commit['worktree']), 'rev-parse', 'HEAD')
    replace_output(ref, 'commit_initial_repair', commit)
    replace_output(ref, 'test_local', test)
    if recheck:
        with sqlite3.connect(ref['db']) as conn:
            for old, new in [('commit_initial_repair', 'commit_test_repair'), ('test_local', 'test_local_recheck')]:
                conn.execute('UPDATE processes SET id=?, output_json=replace(output_json, ?, ?) WHERE id=?', (
                    'pr_repair:' + new, 'pr_repair:' + old, 'pr_repair:' + new, 'pr_repair:' + old))


@pytest.mark.parametrize('corrupt', [None, 'argv', 'scope', 'identity', 'red', 'terminal'])
def test_actual_scoped_green_journal_crosses_checkpoint(tmp_path, monkeypatch, corrupt):
    inputs, outputs, ref, _ = evidence(tmp_path)
    work = Path(outputs['worktree_add']['worktree'])
    test = real_tests(tmp_path, monkeypatch, inputs, work, scoped=True)
    assert test['full_suite_returncode'] == 1
    # Supply exact revision authority for the fixture-created repair too.
    start = git(work, 'rev-parse', 'HEAD^')
    target = git(work, 'rev-parse', 'HEAD')
    inputs['head_sha'] = inputs['reviewed_head_sha'] = start
    inputs['review']['reviewed_head_sha'] = start
    outputs['worktree_add'].update(repair_start_head_sha=start, worktree_head_sha=start)
    replace_output(ref, 'worktree_add', outputs['worktree_add'])
    before = {'head': start, 'branch': inputs['branch'], 'origin': 'https://github.com/o/r.git'}
    replace_output(ref, 'run_agent', {**outputs['run_agent'], 'revision': {'before': before, 'after': before}})
    outputs['commit_initial_repair']['revision'] = {
        'before': before, 'after': {**before, 'head': target}, 'parents': [start]}
    with sqlite3.connect(ref['db']) as conn:
        conn.execute('UPDATE processes SET input_json=?', (json.dumps(inputs),))
    bind_tests(ref, outputs, test, recheck=True)
    rows = checkpoint._rows(test, 'test_local_execution')
    if corrupt == 'identity':
        with sqlite3.connect(test['db']) as conn:
            conn.execute("UPDATE processes SET input_json=? WHERE id='test_local_execution:run_changed_scope_tests'",
                         (json.dumps({'repo': 'wrong/repo', 'worktree': str(work), 'changed_scope': True}),))
    elif corrupt:
        name, field, value = {
            'argv': ('run_changed_scope_tests', 'argv', ['true']),
            'scope': ('derive_changed_test_scope', 'argv', ['true']),
            'red': ('run_changed_scope_tests', 'returncode', 1),
            'terminal': ('select_test_terminal', 'result', {**rows['select_test_terminal']['output']['result'], 'tests': 'true'}),
        }[corrupt]
        replace_output(test, name, {**rows[name]['output'], field: value})
    result = checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2)
    assert result['route'] == ('fail_closed' if corrupt else 'checkpointed'), result
    if corrupt is None:
        # The same scoped success must agree with its real cache-hit terminal.
        from lokay.proc.test_local_execution_subflow import run
        cached = run(worktree=str(work), changed_scope=True, repo=inputs['repo'], issue=42)
        assert cached['cached'] is True and cached['tested'] is True, cached
        replace_output(ref, 'test_local_recheck', cached)
        assert checkpoint.derive(inputs=inputs, run_ref=ref)['test']['run_id'] == cached['run_id']


@pytest.mark.parametrize('stage', ['initial', 'test', 'bridge'])
@pytest.mark.parametrize('damage', [None, 'unrelated', 'historical'])
def test_deterministic_commit_requires_exact_host_transition(tmp_path, monkeypatch, stage, damage):
    from lokay.agent import run_agent
    from lokay.config import Config
    from lokay.graph_run import run_path
    from lokay.organ.publication import handle_publication
    from lokay.proc import test_local_execution_subflow as subflow
    from lokay.runner import Runner

    inputs, outputs, ref, _ = evidence(tmp_path)
    work = Path(outputs['worktree_add']['worktree'])
    (work / 'pyproject.toml').write_text('[tool.lokay]\ntest = ["true"]\n')
    git(work, 'add', '.')
    git(work, 'commit', '-m', 'test declaration')
    start = git(work, 'rev-parse', 'HEAD')
    inputs['head_sha'] = inputs['reviewed_head_sha'] = start
    inputs['review']['reviewed_head_sha'] = start
    outputs['worktree_add'].update(repair_start_head_sha=start, worktree_head_sha=start)
    replace_output(ref, 'worktree_add', outputs['worktree_add'])
    with sqlite3.connect(ref['db']) as conn:
        conn.execute('UPDATE processes SET input_json=?', (json.dumps(inputs),))
    git(work, 'update-ref', 'refs/remotes/origin/ai/fix/42', start)
    git(work, 'branch', '--set-upstream-to=origin/ai/fix/42')
    monkeypatch.setattr('lokay.proc.commit_all.mutations_allowed', lambda **kw: True)
    monkeypatch.setattr('lokay.proc.commit_all.load_cfg', lambda args: Config())
    monkeypatch.setattr(subflow, 'run_path', lambda **kw: run_path(
        **kw, db_path=tmp_path / 'native-tests'))
    produced = None
    for index in range(1 if stage == 'initial' else 2):
        name = 'run_agent' if index == 0 else 'pr_test_repair_agent'
        agent = run_agent(Runner(), Config(
            agent='test-harness', agent_command=sys.executable,
            agent_args=['-c', f"from pathlib import Path; Path('source').write_text('repair {index}')"],
            executor_enabled=True), worktree=work, prompt='repair', execute=True)
        assert agent['status'] == 'completed' and agent['returncode'] == 0
        insert_output(ref, inputs, name, {'ok': True, **agent} if index == 0 else {'ok': True, 'agent': agent})
        damaged_stage = index == (1 if stage == 'test' else 0)
        if damage == 'unrelated' and damaged_stage:
            # Keep the authorized repair dirty while inserting an unobserved X.
            (work / 'unrelated').write_text('not authorized by the harness')
            git(work, 'add', 'unrelated')
            git(work, 'commit', '-m', 'unrelated X', '--', 'unrelated')
        produced = handle_publication('commit_all', {**inputs, 'repair_run_ref': ref}, {
            'worktree_add': outputs['worktree_add'], 'assert_initial_repair_diff': {'ok': True, 'real': True}},
            {'cfg': [], 'live': ['--live'], 'repo': 'o/r', 'issue_number': 42,
             'pr_number': 57, 'repair_mode': True, 'branch': inputs['branch']})
        assert produced is not None and produced['committed'] is True
        # Feed even a rejected effect into the consumer as a successful historical
        # row: consumer verification must not depend on the producer's ok flag.
        recorded = {**produced, 'ok': True}
        if damage == 'historical' and damaged_stage:
            recorded.pop('revision', None)
        if index == 0:
            replace_output(ref, 'commit_initial_repair', recorded)
        else:
            insert_output(ref, inputs, 'commit_test_repair', recorded)
    tested = subflow.run(worktree=str(work), changed_scope=False, repo='o/r', issue=42)
    assert tested['ok'] is True and tested['tested'] is True
    if stage == 'initial':
        replace_output(ref, 'test_local', tested)
    else:
        insert_output(ref, inputs, 'test_local_recheck', tested)
    persisted = checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2)
    monkeypatch.setattr('lokay.graph_run.pr_journal_dir', lambda *args: Path(ref['db']).parent)
    recovered = checkpoint.recover_legacy(repo='o/r', pr=57, branch=inputs['branch'],
                                          state_dir=tmp_path / 'discovery', budget=2)
    assert produced is not None
    if damage:
        assert persisted['route'] == 'fail_closed', persisted
        assert recovered['route'] != 'checkpointed', recovered
        if damage == 'unrelated' or stage == 'bridge':
            assert produced['ok'] is False, produced
    else:
        assert produced['ok'] is True, produced
        assert persisted['route'] == recovered['route'] == 'checkpointed'
        assert checkpoint.derive(inputs=inputs, run_ref=ref)['intent']['target_head_sha'] == git(work, 'rev-parse', 'HEAD')


@pytest.mark.parametrize('corrupt', [None, 'missing', 'start', 'branch', 'repo', 'task', 'target', 'legacy'])
def test_actual_agent_commit_producer_crosses_checkpoint(tmp_path, monkeypatch, corrupt):
    from lokay.agent import run_agent
    from lokay.config import Config
    from lokay.organ.publication import handle_publication
    from lokay.runner import Runner

    inputs, outputs, ref, _ = evidence(tmp_path)
    work = Path(outputs['worktree_add']['worktree'])
    # The admitted starting point is the exact head at harness entry, not ancestry.
    (work / 'pyproject.toml').write_text('[tool.lokay]\ntest = ["true"]\n')
    git(work, 'add', '.')
    git(work, 'commit', '-m', 'declared test baseline')
    start = git(work, 'rev-parse', 'HEAD')
    inputs['head_sha'] = inputs['reviewed_head_sha'] = start
    inputs['review']['reviewed_head_sha'] = start
    outputs['worktree_add'].update(repair_start_head_sha=start, worktree_head_sha=start)
    replace_output(ref, 'worktree_add', outputs['worktree_add'])
    with sqlite3.connect(ref['db']) as conn:
        conn.execute('UPDATE processes SET input_json=?', (json.dumps(inputs),))
    cfg = Config(agent='test-harness', agent_command=sys.executable,
                 agent_args=['-c', "from pathlib import Path; import subprocess; Path('source').write_text('agent repair'); subprocess.run(['git','commit','-am','agent repair'],check=True)"],
                 executor_enabled=True)
    agent = run_agent(Runner(), cfg, worktree=work, prompt='repair', execute=True)
    agent_inputs = dict(inputs)
    if corrupt == 'missing':
        agent.pop('revision', None)
    elif corrupt in {'start', 'branch', 'repo'}:
        field = {'start': 'head', 'branch': 'branch', 'repo': 'origin'}[corrupt]
        agent['revision']['before'][field] = 'unverified'
    elif corrupt == 'task':
        agent_inputs['task'] = {**inputs['task'], 'number': 99}
    elif corrupt == 'target':
        (work / 'source').write_text('unrelated post-agent commit')
        git(work, 'commit', '-am', 'unrelated')
    insert_output(ref, agent_inputs, 'run_agent', {'ok': True, **agent})
    monkeypatch.setattr('lokay.proc.commit_all.mutations_allowed', lambda **kw: True)
    monkeypatch.setattr('lokay.proc.commit_all.load_cfg', lambda args: Config())
    git(work, 'update-ref', 'refs/remotes/origin/ai/fix/42', start)
    git(work, 'branch', '--set-upstream-to=origin/ai/fix/42')
    produced = handle_publication('commit_all', {**inputs, 'repair_run_ref': ref}, {
        'worktree_add': outputs['worktree_add'], 'assert_initial_repair_diff': {'ok': True, 'real': True}},
        {'cfg': [], 'live': ['--live'], 'repo': 'o/r', 'issue_number': 42,
         'pr_number': 57, 'repair_mode': True, 'branch': inputs['branch']})
    assert produced is not None
    if corrupt not in {None, 'legacy'}:
        assert produced['ok'] is False and produced['committed'] is False, produced
        return
    assert produced['committed_by'] == 'agent'
    assert produced['commit'] == git(work, 'rev-parse', 'HEAD'), produced
    if corrupt == 'legacy':
        # Empty historical commit output is usable only with equivalent durable
        # exact-target host observations. No HEAD/descendant fallback.
        produced['commit'] = ''
    replace_output(ref, 'commit_initial_repair', produced)
    # Run the real native verifier on the exact agent-created target.
    from lokay.graph_run import run_path
    from lokay.proc import test_local_execution_subflow as subflow
    monkeypatch.setattr(subflow, 'run_path', lambda **kw: run_path(
        **kw, db_path=tmp_path / 'native-tests'))
    tested = subflow.run(worktree=str(work), changed_scope=False, repo=inputs['repo'], issue=42)
    assert tested['ok'] is True and tested['tested'] is True, tested
    replace_output(ref, 'test_local', tested)
    result = checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2)
    assert result['route'] == 'checkpointed', result
    # Recovery reads this same journal, never a fresh HEAD as authority.
    monkeypatch.setattr('lokay.graph_run.pr_journal_dir', lambda *args: Path(ref['db']).parent)
    recovered = checkpoint.recover_legacy(repo='o/r', pr=57, branch=inputs['branch'],
                                          state_dir=tmp_path / 'recovery', budget=2)
    assert recovered['route'] == 'checkpointed', recovered
    with sqlite3.connect(ref['db']) as conn:
        raw = conn.execute("SELECT output_json FROM processes WHERE id='pr_repair:run_agent'").fetchone()[0]
    envelope = json.loads(raw)
    envelope['payload'].pop('revision')
    replace_output(ref, 'run_agent', envelope['payload'])
    refused = checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path / 'unverified', budget=2)
    assert refused['route'] == 'fail_closed', refused
