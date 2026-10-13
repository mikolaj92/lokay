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
from lokay.build import _git

with tempfile.TemporaryDirectory() as tmp, patch.object(state, 'RUNS', Path(tmp) / 'runs'):
    root = Path(tmp) / 'repo'
    root.mkdir()
    _git(root, ['init', '-b', 'lokay/7'])
    _git(root, ['config', 'user.name', 'fixture'])
    _git(root, ['config', 'user.email', 'fixture@example.test'])
    (root / 'code.py').write_text('old\n')
    _git(root, ['add', '.']); _git(root, ['commit', '-m', 'base'])
    _git(root, ['update-ref', 'refs/remotes/origin/main', 'HEAD'])
    old = _git(root, ['rev-parse', 'HEAD'])
    (root / 'test_added.py').write_text('new\n')
    _git(root, ['add', '.']); _git(root, ['commit', '-m', 'new'])
    head = _git(root, ['rev-parse', 'HEAD'])
    assert old != head
    picked = {'repo': 'example/repo', 'issue': 7}
    tests = ['pytest']
    log = 'STALE FAILURE\nFAILED test_added.py::test_new - AssertionError\n'
    findings = [{'plik': 'code.py', 'pytanie': 'tests'}]
    fingerprint = hashlib.sha256(json.dumps(sorted({json.dumps(['code.py', 'tests', None])})).encode()).hexdigest()

    def reset(ci_sha, node='check', **fields):
        state.state_update(picked['repo'], 7, node=node, sha=head,
            local_ci={'sha': ci_sha, 'argv': tests, 'result': 'red', 'log': log,
                      'failed': [], 'notes': []}, test_log=log,
            verdict={'sha': head, 'result': 'fix', 'uwagi': findings},
            fix_fingerprint=None, issue_title='title', issue_body='', **fields)

    reset(old)
    assert start.fix_to_build(picked, root) is None, 'stale CI redirected to Build'
    reset(head)
    assert start.fix_to_build(picked, root) == {'next': 'build'}

    real_git = __import__('lokay.git', fromlist=['_git'])._git
    def git(path, args):
        if args[0] in ('fetch', 'merge'):
            return 0, '', ''
        return real_git(path, args)

    with ExitStack() as stack:
        stack.enter_context(patch('lokay.start.load_repos', return_value=[
            {'name': picked['repo'], 'clone_path': str(root)}]))
        stack.enter_context(patch('lokay.git._git', side_effect=git))
        stack.enter_context(patch('lokay.fix.fix_publish', side_effect=lambda *a:
            {'result': 'pushed', 'sha': a[2]}))
        stack.enter_context(patch('lokay.start.pushed_pr', return_value={'number': 1}))
        stack.enter_context(patch('lokay.start.refresh_body', return_value={'result': 'updated'}))
        stack.enter_context(patch('lokay.gh.open_pr_for', return_value={'number': 1}))
        stack.enter_context(patch('lokay.gh.pr_checks', return_value={'result': 'pending'}))
        stack.enter_context(patch('lokay.gh.check_comment'))
        stack.enter_context(patch('lokay.setup.prepare_dependencies'))

        def rerun(sha, commands, worktree):
            saved = state.state_read(picked['repo'], 7)
            assert saved['local_ci'] is None and saved['test_log'] is None, saved
            assert commands == [tests] and worktree == root
            return {'sha': sha, 'result': 'green', 'log': 'fresh', 'failed': [], 'notes': []}

        # Each mismatch invalidates CI; matching SHA reuses it.
        for ci_sha, published_sha, expected in ((old, head, 1), (old, old, 1), (head, old, 1), (head, head, 0)):
            reset(ci_sha)
            with patch('lokay.check.local_ci', side_effect=rerun) as ci:
                assert start._finish(picked, root, 'lokay/7', published_sha, tests)['result'] == 'pending'
                assert ci.call_count == expected, (ci_sha, published_sha, ci.call_count)

        # Both Fix and replan prompts omit stale logs, but retain current logs.
        for ci_sha in (old, head):
            for replan in (False, True):
                reset(ci_sha, node='fix')
                if replan:
                    state.state_update(picked['repo'], 7, fix_fingerprint=fingerprint, fix_counts=[1, 1])
                def fix(worktree, sha, prompt, *args, **kwargs):
                    assert (log in prompt) == (ci_sha == head), prompt
                    return {'result': 'failed', 'reason': 'fixture'}
                with patch('lokay.fix.fix_code', side_effect=fix) as code, \
                     patch('lokay.start._prepare', return_value={'result': 'fixture'}) as prepare:
                    result = start._finish(picked, root, 'lokay/7', head, tests)
                if replan and ci_sha == head:
                    assert result == {'next': 'build'}
                elif replan:
                    prepare.assert_called_once()
                    assert log not in state.state_read(picked['repo'], 7)['plan_prompt']
                else:
                    code.assert_called_once()
print('stale_ci: redirect, both SHA checks, invalidation, rerun/reuse, Fix/Plan prompts OK')
PY
