#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
uv run --offline python - <<'PY'
import hashlib
import json
import tempfile
from contextlib import ExitStack
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch
from lokay import start, state
from lokay.build import _git, build_code
from lokay.run import run_process

with tempfile.TemporaryDirectory() as tmp, patch.object(state, 'RUNS', Path(tmp) / 'runs'):
    root = Path(tmp) / 'repo'
    root.mkdir()
    _git(root, ['init', '-b', 'lokay/7'])
    _git(root, ['config', 'user.name', 'fixture'])
    _git(root, ['config', 'user.email', 'fixture@example.test'])
    (root / 'code.py').write_text('old\n')
    (root / 'test_existing.py').write_text('existing\n')
    _git(root, ['add', '.']); _git(root, ['commit', '-m', 'base'])
    _git(root, ['update-ref', 'refs/remotes/origin/main', 'HEAD'])
    added = root / 'package/tests/test_added.py'
    added.parent.mkdir(parents=True)
    added.write_text('new\n')
    _git(root, ['add', '.']); _git(root, ['commit', '-m', 'added test'])
    sha = _git(root, ['rev-parse', 'HEAD'])
    picked = {'repo': 'example/repo', 'issue': 7, 'node': 'check'}
    findings = [{'plik': 'code.py', 'pytanie': 'tests'}]
    log = 'failure details\nFAILED tests/test_added.py::test_new - AssertionError\n'
    def reset(**fields):
        state.state_update(picked['repo'], 7, node='fix', sha=sha,
            verdict={'sha': sha, 'result': 'fix', 'uwagi': findings},
            plan_accepted_sha='accepted', fix_fingerprint=None, fix_counts=[], build_note=None,
            test_log=log, local_ci={'result': 'red', 'sha': sha, 'log': log}, **fields)
    for no_progress in (False, True):
        reset()
        if no_progress:
            state.state_update(picked['repo'], 7, fix_counts=[1, 1])
        with ExitStack() as stack:
            stack.enter_context(patch('lokay.start.load_repos', return_value=[
                {'name': picked['repo'], 'clone_path': str(root)}]))
            stack.enter_context(patch('lokay.setup.prepare_dependencies'))
            fix = stack.enter_context(patch('lokay.fix.fix_code', return_value={
                'result': 'failed', 'reason': 'no_changes'}))
            stack.enter_context(patch('lokay.start._prepare', side_effect=AssertionError('Plan forbidden')))
            result = start._finish(picked, root, 'lokay/7', sha, ['pytest'])
        assert result == {'next': 'build'}, result
        assert fix.call_count == (0 if no_progress else 1)
        saved = state.state_read(picked['repo'], 7)
        assert saved['node'] == 'build' and saved['plan_accepted_sha'] == 'accepted', saved
        assert 'package/tests/test_added.py' in saved['build_note']
        assert 'failure details' in saved['build_note'] and 'new unit tests are not allowed' in saved['build_note']
        assert saved['retry_at'] == 0
        assert 'Fix → Build: failing test added in this PR: package/tests/test_added.py' in (state.run_dir(picked['repo'], 7) / 'rounds.md').read_text()
    # Existing tests and green CI do not redirect.
    for failure_log, result in [('FAILED test_existing.py::test_old', 'red'), (log, 'green')]:
        reset()
        state.state_update(picked['repo'], 7, local_ci={'result': result, 'log': failure_log})
        assert start.fix_to_build(picked, root) is None
    reset()
    start.fix_to_build(picked, root)
    note = state.state_read(picked['repo'], 7)['build_note']
    def pi(argv, **kwargs):
        if argv[0] != 'pi' and not (argv[0] == '/usr/bin/sandbox-exec' and 'pi' in argv):
            return run_process(argv, **kwargs)
        assert note in argv[-1], argv
        added.unlink()
        return CompletedProcess(argv, 0, '', '')
    with patch('lokay.build.run_process', side_effect=pi):
        result = build_code(root, 'plan', 'fix', '', {}, build_note=note)
    assert result['result'] == 'done', result
    assert not added.exists()
    assert _git(root, ['diff', '--name-only', 'origin/main...HEAD']) == ''
    # Successful Build consumes its note, without invalidating the accepted plan.
    from lokay import plan
    art = state.run_dir(picked['repo'], 7) / 'plan.md'
    art.write_text('accepted plan')
    accepted = hashlib.sha256(art.read_bytes()).hexdigest()
    state.state_update(picked['repo'], 7, issue_title='fix', issue_body='', plan_accepted_sha=accepted)
    with patch('lokay.start.load_repos', return_value=[{'name': picked['repo'], 'clone_path': str(root)}]), \
         patch('lokay.plan.valid_plan', return_value=True), \
         patch('lokay.setup.prepare_dependencies'), \
         patch('lokay.git.worktree_add', return_value={'result': 'added'}), \
         patch('lokay.build.build_code', return_value={'result': 'done'}) as build, \
         patch('lokay.build.build_publish', return_value={'result': 'pr_open', 'sha': 'next', 'pr': 1}), \
         patch('lokay.start.open_pr_for', return_value=None):
        start._prepare({**picked, 'node': 'build'})
    assert build.call_args.kwargs['build_note'] == note
    assert state.state_read(picked['repo'], 7)['build_note'] is None
    assert state.state_read(picked['repo'], 7)['plan_accepted_sha'] == accepted
print('fix_to_build: no_changes, no-progress, package paths, prompt, deletion, clearing OK')
PY
