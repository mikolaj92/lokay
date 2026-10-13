#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
uv run python - <<'PY'
import subprocess
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from lokay import start, state
from lokay.merge_guard import merge_guard

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    origin, worktree = root / 'origin.git', root / 'worktree'
    def git(*args):
        return subprocess.check_output(['git', *map(str, args)], text=True, stderr=subprocess.STDOUT).strip()
    def local(*args):
        return git('-C', worktree, *args)
    git('init', '--bare', '-b', 'main', origin)
    git('clone', origin, worktree)
    local('config', 'user.name', 'mikolaj92')
    local('config', 'user.email', 'fixture@example.invalid')
    (worktree / 'code.py').write_text('pass\n')
    (worktree / 'pyproject.toml').write_text('[project]\n')
    (worktree / 'uv.lock').write_text('original\n')
    (worktree / 'tracked.log').write_text('baseline\n')
    local('add', '.')
    local('commit', '-m', 'fixture')
    local('push', 'origin', 'main')
    base = local('rev-parse', 'HEAD')

    def finish(branch, title, body, dirty, artifacts=()):
        local('checkout', '-b', branch, base)
        if artifacts:
            for name in artifacts:
                file = worktree / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('junk\n')
            local('add', '.')
            local('commit', '-m', 'earlier artifacts')
        if dirty:
            (worktree / 'tests').mkdir(exist_ok=True)
            (worktree / 'tests' / 'new test.py').write_text('assert True\n')
            (worktree / 'uv.lock').write_text('unrelated\n')
            if 'test' in title:
                (worktree / 'pyproject.toml').write_text('[project]\nname = "fixture"\n')
        (worktree / 'code.py').write_text('value = 1\n')
        local('add', '.')
        local('commit', '-m', 'change')
        local('push', 'origin', branch)
        sha = local('rev-parse', 'HEAD')
        picked = {'repo': 'example/repo', 'issue': 1}
        with ExitStack() as stack:
            stack.enter_context(patch('lokay.state.RUNS', root / branch / 'runs'))
            state.state_update('example/repo', 1, node='check', issue_title=title, issue_body=body)
            stack.enter_context(patch('lokay.start.load_repos', return_value=[
                {'name': 'example/repo', 'clone_path': str(worktree)}]))
            stack.enter_context(patch('lokay.start.pushed_pr', return_value=True))
            stack.enter_context(patch('lokay.start.refresh_body', return_value={'result': 'updated'}))
            stack.enter_context(patch('lokay.gh.open_pr_for', side_effect=lambda *a:
                {'number': 1, 'headRefOid': local('rev-parse', 'HEAD')}))
            stack.enter_context(patch('lokay.gh.pr_checks', return_value={'result': 'green', 'failed': []}))
            stack.enter_context(patch('lokay.gh.check_comment', return_value={'result': 'done'}))
            stack.enter_context(patch('lokay.check.decide_batches', return_value={'next': 'ok', 'uwagi': []}))
            merge = stack.enter_context(patch('lokay.merge.merge_sha', return_value={
                'result': 'merged', 'merge_sha': sha}))
            outcome = start._finish(picked, worktree, branch, sha, ['true'])
            saved = state.state_read('example/repo', 1)
            if artifacts:
                assert outcome['result'] == 'check', outcome
                merge.assert_not_called()
                assert saved['node'] == 'check' and saved['verdict'] is None and saved['local_ci'] is None
                assert not any((worktree / name).exists() for name in artifacts)
                assert local('log', '-1', '--format=%s') == 'lokay merge-guard: drop artifacts'
                assert local('rev-parse', 'HEAD') == local('rev-parse', f'origin/{branch}')
                assert not local('status', '--porcelain')
                assert merge_guard(worktree, title, body) == {'removed': [], 'reset': []}
                outcome = start._finish(picked, worktree, branch, local('rev-parse', 'HEAD'), ['true'])
                assert outcome['result'] == 'merged', outcome
                merge.assert_called_once()
            elif dirty and 'test' not in title:
                assert outcome['result'] == 'check', outcome
                merge.assert_not_called()
                assert saved['node'] == 'check' and saved['verdict'] is None and saved['local_ci'] is None
                assert not (worktree / 'tests' / 'new test.py').exists()
                assert (worktree / 'uv.lock').read_text() == 'original\n'
                assert local('log', '-1', '--format=%s') == 'lokay merge-guard: drop new tests / reset lockfiles'
                assert local('rev-parse', 'HEAD') == local('rev-parse', f'origin/{branch}')
                assert not local('status', '--porcelain')
                log = (state.run_dir('example/repo', 1) / 'rounds.md').read_text()
                assert 'Merge guard: removed tests/new test.py, reset uv.lock' in log
                assert merge_guard(worktree, '', '') == {'removed': [], 'reset': []}
            else:
                assert outcome['result'] == 'merged', outcome
                merge.assert_called_once()
                if dirty:
                    assert (worktree / 'tests' / 'new test.py').exists()
    finish('guard', 'Fix code', '', True)
    finish('requested-merge', 'Add test coverage', '', True)
    # A requested test and its changed manifest preserve the lockfile.
    local('checkout', 'main')
    local('checkout', '-b', 'requested', base)
    (worktree / 'test_requested.py').write_text('assert True\n')
    (worktree / 'pyproject.toml').write_text('[project]\nname = "fixture"\n')
    (worktree / 'uv.lock').write_text('updated\n')
    local('add', '.')
    local('commit', '-m', 'requested test')
    assert merge_guard(worktree, 'Dodaj testy', '') == {'removed': [], 'reset': []}
    assert merge_guard(worktree, '', 'Add regression coverage') == {'removed': [], 'reset': []}
    finish('artifacts', 'Add test coverage', '', False, (
        'tracked.log', 'nested/suite.log', '.check-local/suite.log',
        '.check-local/validation.log', '.check-local/tmp/uv-1.lock',
        '.check-local/bin/gh', '.check-local/ignore', 'tmp/uv-2.lock',
        'tmp/nested/uv-3.lock', 'tmp/uv.lock', 'bin/gh', 'nested/bin/gh'))
    finish('clean', 'Fix code', '', False)
print('merge guard: removed/reset → committed/pushed → Check; requested tests kept; clean → Merge OK')
PY
