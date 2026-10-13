#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
uv run --offline python - <<'PY'
import subprocess
import tempfile
from pathlib import Path
from lokay.build import tidy_and_commit, pr_body, worktree_status, generated_cleanup
from lokay.gh import pr_set_body
from lokay.start import refresh_body
from unittest.mock import patch

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root, text=True).strip()
    git('init', '-q')
    git('config', 'user.name', 'mikolaj92')
    git('config', 'user.email', 'fixture@example.com')
    for path in ('uv.lock', 'pyproject.toml', 'keep/__pycache__/tracked.pyc'):
        file = root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text('original\n')
    git('add', '-A'); git('commit', '-qm', 'base')
    git('update-ref', 'refs/remotes/origin/main', 'HEAD')
    (root / 'uv.lock').write_text('junk\n')
    (root / 'test_new.py').write_text('new test\n')
    for path in ('pkg/__pycache__/a.pyc', '.pytest_cache/a', '.ruff_cache/a',
                 '.mypy_cache/a', '.venv/bin/python', 'a.pyc', 'keep/__pycache__/junk.pyc'):
        file = root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text('cache')
    committed, junk = tidy_and_commit(root, 'tidy fixture')
    assert committed == ['test_new.py'] and junk == ['uv.lock'], (committed, junk)
    assert (root / 'uv.lock').read_text() == 'original\n'
    assert not (root / 'pkg/__pycache__').exists()
    assert not (root / '.venv').exists()
    assert (root / 'keep/__pycache__/tracked.pyc').exists()
    assert git('status', '--porcelain') == ''
    assert tidy_and_commit(root, 'noop') == ([], [])
    # A changed manifest protects its sibling lock, including earlier commits.
    (root / 'pyproject.toml').write_text('changed\n')
    (root / 'uv.lock').write_text('valid\n')
    assert tidy_and_commit(root, 'dependencies') == (['pyproject.toml', 'uv.lock'], [])
    (root / 'uv.lock').write_text('valid again\n')
    assert tidy_and_commit(root, 'lock update') == (['uv.lock'], [])
    # Local CI artifacts, including ignored and staged files, never reach the commit.
    (root / '.gitignore').write_text('.check-local/\n')
    (root / 'tracked.log').write_text('tracked\n')
    (root / 'tmp').mkdir()
    (root / 'tmp/tracked.lock').write_text('original\n')
    git('add', '-A'); git('commit', '-qm', 'artifact baseline')
    (root / 'tracked.log').write_text('keep tracked log edits\n')
    (root / 'tmp/tracked.lock').write_text('incidental\n')
    artifacts = ('.check-local/suite.log', '.check-local/validation.log',
                 '.check-local/tmp/uv-1.lock', '.check-local/bin/gh', '.check-local/ignore',
                 'suite.log', 'nested/validation.log', 'tmp/uv-2.lock',
                 'tmp/nested/uv-3.lock', 'bin/gh', 'nested/bin/gh')
    for name in artifacts:
        file = root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text('junk\n')
    git('add', '-f', '.check-local/ignore', 'suite.log', 'bin/gh')
    (root / 'code.py').write_text('pass\n')
    committed, junk = tidy_and_commit(root, 'artifact cleanup')
    assert committed == ['code.py', 'tracked.log'], (committed, junk)
    assert not any((root / name).exists() for name in artifacts)
    assert not (root / '.check-local').exists()
    assert (root / 'tmp/tracked.lock').read_text() == 'original\n'
    assert git('status', '--porcelain') == ''
    assert tidy_and_commit(root, 'artifact noop') == ([], [])
    # Only pi edits enter the commit, not earlier staged or untracked files.
    (root / 'earlier.txt').write_text('keep staged\n')
    git('add', 'earlier.txt')
    (root / 'setup.txt').write_text('keep untracked\n')
    before = worktree_status(root)
    (root / 'code.py').write_text('pi edit\n')
    (root / '.validation/current-fix').mkdir(parents=True)
    (root / '.validation/current-fix/output').write_text('generated\n')
    assert tidy_and_commit(root, 'pi only', before)[0] == ['code.py']
    assert git('diff', '--cached', '--name-only') == 'earlier.txt'
    assert (root / 'setup.txt').exists()
    assert not (root / '.validation/current-fix/output').exists()
    # CI restores the accepted lock even when dependencies changed in this PR.
    lock = (root / 'uv.lock').read_text()
    with generated_cleanup(root):
        (root / 'uv.lock').write_text('CI rewrite\n')
        (root / 'ci-output.txt').write_text('generated\n')
    assert (root / 'uv.lock').read_text() == lock
    assert not (root / 'ci-output.txt').exists()
    assert (root / 'setup.txt').exists()
    git('reset', '-q', '--', 'earlier.txt')
    (root / 'earlier.txt').unlink(); (root / 'setup.txt').unlink()
    # A lock committed by pi without its manifest is reset before publishing.
    main = git('rev-parse', 'origin/main')
    git('update-ref', 'refs/remotes/origin/main', 'HEAD')
    (root / 'uv.lock').write_text('pi rewrite\n')
    git('add', 'uv.lock'); git('commit', '-qm', 'pi lock')
    assert tidy_and_commit(root, 'reset pi lock')[0] == ['uv.lock']
    assert (root / 'uv.lock').read_text() == lock
    git('update-ref', 'refs/remotes/origin/main', main)
    plan = Path(tmp).parent / (root.name + '-plan.md')
    try:
        plan.write_text('# Plan\n\n## Cel\nShip the change.\n\n## Kroki\nSECRET\n')
        body = pr_body(root, plan)
        assert '## Zmiany' in body and 'test_new.py' in body and '- lock update' in body
        assert '## Plan\n\n## Cel\nShip the change.' in body and 'SECRET' not in body
        with patch('lokay.gh._gh', return_value=(0, '', '')) as gh:
            assert pr_set_body('example/repo', 12, body, 7)['result'] == 'updated'
            args = gh.call_args.args[0]
            assert args[:6] == ['pr', 'edit', '12', '--repo', 'example/repo', '--body']
            assert args[6] == body.rstrip() + '\n\nCloses #7\n\nOpened by lokay.\n'
        with patch('lokay.start.load_repos', return_value=[{'name': 'example/repo', 'clone_path': str(root / 'main')}]), \
             patch('lokay.start.open_pr_for', return_value={'number': 12}) as lookup, \
             patch('lokay.start.run_dir', return_value=plan.parent), \
             patch('lokay.build.pr_body', return_value=body) as builder, \
             patch('lokay.gh.pr_set_body', return_value={'result': 'updated'}) as setter:
            assert refresh_body('example/repo', 7) == {'result': 'updated'}
            lookup.assert_called_once_with('example/repo', 'lokay/7')
            builder.assert_called_once_with(root / 'main-wt-7', plan.parent / 'plan.md', '')
            setter.assert_called_once_with('example/repo', 12, body, 7)
    finally:
        plan.unlink(missing_ok=True)
print('tidy: junk reset, caches removed, changes committed, dependency locks kept, diff body OK')
PY
