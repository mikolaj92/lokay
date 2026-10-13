#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT
export HOME="$root/home"
mkdir -p "$HOME"
uv run --offline python - <<'PY'
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from lokay import start, state


def git(path, *args):
    return subprocess.check_output(['git', *args], cwd=path, stderr=subprocess.STDOUT, text=True).strip()


with tempfile.TemporaryDirectory() as tmp:
    for case in ('equal', 'ahead', 'dirty', 'behind', 'diverged', 'conflict', 'stale_pr', 'delayed_pr'):
        root = Path(tmp) / case
        root.mkdir()
        remote = root / 'remote.git'
        clone = root / 'main'
        worktree = root / 'main-wt-7'
        peer = root / 'peer'
        git(root, 'init', '--bare', str(remote))
        git(root, 'clone', str(remote), str(clone))
        git(clone, 'config', 'user.name', 'mikolaj92')
        git(clone, 'config', 'user.email', 'scenario@example.invalid')
        (clone / 'shared.txt').write_text('base\n')
        git(clone, 'add', '.')
        git(clone, 'commit', '-m', 'base')
        git(clone, 'branch', '-M', 'main')
        git(clone, 'push', 'origin', 'main')
        git(clone, 'worktree', 'add', '-b', 'lokay/7', str(worktree))
        git(worktree, 'push', 'origin', 'lokay/7')
        base = git(worktree, 'rev-parse', 'HEAD')
        git(root, 'clone', '--branch', 'lokay/7', str(remote), str(peer))
        git(peer, 'config', 'user.name', 'mikolaj92')
        git(peer, 'config', 'user.email', 'scenario@example.invalid')

        def commit(path, name, text):
            (path / name).write_text(text)
            git(path, 'add', '.')
            git(path, 'commit', '-m', text.strip())

        if case in ('ahead', 'diverged', 'conflict', 'stale_pr', 'delayed_pr'):
            commit(worktree, 'shared.txt' if case == 'conflict' else 'local.txt', 'local\n')
        if case == 'dirty':
            (worktree / 'dirty.txt').write_text('uncommitted\n')
        if case in ('behind', 'diverged', 'conflict'):
            commit(peer, 'shared.txt' if case == 'conflict' else 'remote.txt', 'remote\n')
            git(peer, 'push', 'origin', 'lokay/7')
        initial_remote = git(remote, 'rev-parse', 'refs/heads/lokay/7')
        initial_local = git(worktree, 'rev-parse', 'HEAD')
        repo = f'example/{case}'
        picked = {'repo': repo, 'issue': 7, 'pr': 12, 'node': 'check'}

        pr_calls = 0
        def pr(*args):
            global pr_calls
            pr_calls += 1
            sha = initial_remote if case == 'stale_pr' or (case == 'delayed_pr' and pr_calls <= 3) else git(remote, 'rev-parse', 'refs/heads/lokay/7')
            return {'number': 12, 'headRefOid': sha}

        with patch('lokay.start.load_repos', return_value=[{'name': repo, 'clone_path': str(clone)}]), \
             patch('lokay.start.open_pr_for', side_effect=pr), \
             patch('lokay.start.refresh_body', return_value={'result': 'updated'}) as refresh, \
             patch('lokay.start.time.sleep') as sleep, \
             patch('lokay.start._finish', return_value={'result': 'pending'}) as finish:
            result = start.resume(picked)
            if case in ('conflict', 'stale_pr'):
                assert result['result'] == 'failed', (case, result)
                assert result['reason'] == ('sha diverged: conflict' if case == 'conflict' else 'sha mismatch after push'), result
                finish.assert_not_called()
                saved = state.state_read(repo, 7)
                assert saved['failures'] == 1 and saved['retry_at'] == 0, saved
                if case == 'stale_pr':
                    assert pr_calls == 7 and sleep.call_count == 5
                if case == 'conflict':
                    assert git(remote, 'rev-parse', 'refs/heads/lokay/7') == initial_remote
                continue
            assert result == {'result': 'pending'}, (case, result)
            head = git(worktree, 'rev-parse', 'HEAD')
            assert head == git(remote, 'rev-parse', 'refs/heads/lokay/7'), case
            assert state.state_read(repo, 7)['sha'] == head
            finish.assert_called_once_with(picked, worktree, 'lokay/7', head, [])
            assert refresh.call_count == int(case in ('ahead', 'dirty', 'diverged', 'delayed_pr'))
            if case == 'delayed_pr':
                assert sleep.call_count == 2 and all(call.args == (5,) for call in sleep.call_args_list)
            if case == 'behind':
                assert head == initial_remote and head != initial_local
            if case == 'diverged':
                parents = git(worktree, 'rev-list', '--parents', '-n', '1', 'HEAD').split()[1:]
                assert parents == [initial_local, initial_remote], parents
                assert (worktree / 'local.txt').read_text() == 'local\n'
                assert (worktree / 'remote.txt').read_text() == 'remote\n'
            if case == 'dirty':
                assert head != base and not git(worktree, 'status', '--porcelain')
print('resume push: equal, ahead, dirty, behind, diverged, conflict, stale and delayed PR OK')
PY
