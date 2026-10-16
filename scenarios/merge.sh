set -eu
cd "$(dirname "$0")/.."
root=$(mktemp -d "$PWD/.local/merge.XXXXXX")
trap 'rm -rf "$root"' EXIT HUP INT TERM
mkdir -p "$root/home" "$root/tmp"
HOME="$root/home" TMPDIR="$root/tmp" SCENARIO_ROOT="$root" GIT_CONFIG_COUNT=0 .venv/bin/python - <<'PY'
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from lokay import store, tick
from lokay.build import tidy_and_commit
from lokay.effects import gh, git

root = Path(os.environ['SCENARIO_ROOT'])
for mode in ('clean', 'conflict', 'remote_moved', 'unresolved'):
    directory = root / mode
    directory.mkdir()
    bare, clone, worktree = (directory / name for name in ('origin.git', 'main', 'main-wt-1'))

    def command(path, *args):
        result = subprocess.run(['git', '-C', str(path), *args], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f'{args}: {result.stderr}')
        return result.stdout.strip()

    command(directory, 'init', '--bare', str(bare))
    command(directory, 'clone', str(bare), str(clone))
    command(clone, 'config', 'user.name', 'mikolaj92')
    command(clone, 'config', 'user.email', 'scenario@localhost')
    command(clone, 'checkout', '-b', 'main')
    (clone / 'value').write_text('base\n')
    command(clone, 'add', '--', 'value')
    command(clone, 'commit', '-m', 'Base')
    command(clone, 'push', 'origin', 'main')
    branch = 'lokay/1'
    command(clone, 'worktree', 'add', '-b', branch, str(worktree))
    (worktree / 'value').write_text('branch\n')
    command(worktree, 'add', '--', 'value')
    command(worktree, 'commit', '-m', 'Branch')
    command(worktree, 'push', 'origin', branch)
    old = command(worktree, 'rev-parse', 'HEAD')
    repo = {'name': 'local/scenario', 'clone_path': str(clone), 'setup': [], 'test': []}
    picked = {'repo': repo['name'], 'issue': 1, 'node': 'check'}
    store.RUNS = directory / 'state' / 'runs'
    store.state_update(repo['name'], 1, node='check', sha=old, issue_title='Update value', issue_body='')
    store.write_artifact(store.run_dir(repo['name'], 1) / 'plan.md', '## Cel\nUpdate value\n## Pliki\n- value\n- peer\n')
    merges = Counter()
    reviewed = []
    advanced = []
    repairs = []

    def github(args, env=None):
        if args[:2] == ['pr', 'list']:
            sha = git.remote_sha(worktree, branch, strict=True)
            return 0, json.dumps([{'number': 1, 'headRefName': branch, 'headRefOid': sha}]), ''
        if args[:2] == ['pr', 'merge']:
            sha = args[-1]
            merges[sha] += 1
            assert sum(merges.values()) <= 2, merges
            if mode == 'unresolved':
                return 1, '', 'not mergeable: conflict'
            if not advanced:
                name = 'value' if mode == 'conflict' else 'upstream'
                (clone / name).write_text('main\n')
                command(clone, 'add', '--', name)
                command(clone, 'commit', '-m', 'Advance main')
                command(clone, 'push', 'origin', 'main')
                advanced.append(command(clone, 'rev-parse', 'HEAD'))
            return 1, '', 'not mergeable: conflict'
        if args[:2] == ['pr', 'view']:
            sha = git.remote_sha(worktree, branch, strict=True)
            if args[-1] == 'headRefOid':
                return 0, json.dumps({'headRefOid': sha}), ''
            assert args[-1] == 'statusCheckRollup,headRefOid', args
            if sha != old:
                return 0, json.dumps({'headRefOid': sha, 'statusCheckRollup': [
                    {'status': 'IN_PROGRESS', 'conclusion': '', 'name': 'checks'}]}), ''
            return 0, json.dumps({'headRefOid': sha, 'statusCheckRollup': [
                {'status': 'COMPLETED', 'conclusion': 'SUCCESS', 'name': 'checks'}]}), ''
        if args[:2] in (['pr', 'edit'], ['pr', 'comment']):
            return 0, '', ''
        raise AssertionError(args)

    def decision(request):
        sha = request['state']['sha']
        assert sha == git.remote_sha(worktree, branch, strict=True)
        assert not advanced or sha != old
        reviewed.append(sha)
        answers = {}
        for question in request['questions']:
            choices = question['options']
            winner = 'ok' if 'ok' in choices else 'false' if 'false' in choices else next(iter(choices))
            probabilities = {key: float(key == winner) for key in choices}
            answers[question['id']] = {'choice': winner, 'confidence': 1.0, 'probabilities': probabilities}
        return answers

    def resolve(path, previous, prompt, env, clone_path=None):
        assert mode == 'conflict', mode
        assert 'value' in prompt
        assert not command(path, 'diff', '--name-only', '--diff-filter=U')
        assert not Path(command(path, 'rev-parse', '--git-path', 'MERGE_HEAD')).exists()
        assert not Path(command(path, 'rev-parse', '--git-path', 'rebase-merge')).exists()
        (path / 'value').write_text('main\n')
        committed, junk = tidy_and_commit(path, 'Resolve main')
        assert 'value' in committed, (committed, junk, command(path, 'status', '--porcelain'))
        assert not Path(command(path, 'rev-parse', '--git-path', 'MERGE_HEAD')).exists()
        repairs.append(command(path, 'rev-parse', 'HEAD'))
        return {'result': 'done', 'artifact': repairs[-1]}

    original_git = git._git
    moved = []

    def publish(path, args, timeout=60):
        if mode == 'remote_moved' and args[0] == 'push' and advanced and not moved:
            peer = directory / 'peer'
            command(directory, 'clone', '--branch', branch, str(bare), str(peer))
            command(peer, 'config', 'user.name', 'mikolaj92')
            command(peer, 'config', 'user.email', 'scenario@localhost')
            (peer / 'peer').write_text('preserved\n')
            command(peer, 'add', '--', 'peer')
            command(peer, 'commit', '-m', 'Remote contributor')
            command(peer, 'push', 'origin', branch)
            moved.append(command(peer, 'rev-parse', 'HEAD'))
        return original_git(path, args, timeout)

    with patch.object(tick, 'load_repos', return_value=[repo]), patch.object(gh, '_gh', side_effect=github), patch('lokay.effects.decide.decide', side_effect=decision), patch('lokay.fix.fix_code', side_effect=resolve), patch.object(git, '_git', side_effect=publish):
        outcome = tick._finish(picked, worktree, branch, old, [])
    head = command(worktree, 'rev-parse', 'HEAD')
    if mode == 'unresolved':
        assert outcome['result'] == 'failed', outcome
        assert outcome['reason'] == 'merge conflict persists after main synchronization'
        assert head == old
        assert merges == {old: 1}
        assert set(reviewed) == {old}
        assert store.state_read(repo['name'], 1)['verdict'] is None
        print('unresolved: merge_old_sha=1 repeated_review=0 retry=1')
        continue
    assert outcome == {'result': 'pending', 'sha': head}, outcome
    assert head != old
    assert git.remote_sha(worktree, branch, strict=True) == head
    assert merges == {old: 1}, merges
    assert reviewed and set(reviewed) == {old}, reviewed
    assert store.state_read(repo['name'], 1)['verdict'] is None
    command(worktree, 'merge-base', '--is-ancestor', advanced[0], head)
    if moved:
        assert command(worktree, 'show', moved[0] + ':peer') == 'preserved'
        assert (worktree / 'peer').read_text() == 'preserved\n'
    assert len(repairs) == int(mode == 'conflict')
    assert not command(worktree, 'status', '--porcelain', '--untracked-files=no')
    print(f'{mode}: merge_old_sha={merges[old]} published_new_sha=1 stale_review=0 fix={len(repairs)}')
PY
