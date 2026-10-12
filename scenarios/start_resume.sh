#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT
export HOME="$root/home"
mkdir -p "$HOME"
uv run --offline python - <<'PY'
import io
import json
import tempfile
from contextlib import ExitStack, redirect_stdout, redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from lokay import start, state

class RetryLoop(BaseException):
    pass

def no_sleep(*args):
    raise RetryLoop('unexpected retry')

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    clone = root / 'main'
    worktree = root / 'main-wt-7'
    clone.mkdir()
    worktree.mkdir()
    repo = 'example/repo'
    picked = {'result': 'picked', 'repo': repo, 'issue': 7, 'pr': 12, 'node': 'check', 'held': {'fixture': True}}
    tests = ['bash', 'verify.sh']
    # Match open_pr_for's production contract: branch is its query filter.
    pr = {'number': 12, 'headRefOid': 'new'}

    def reset(**fields):
        path = state.run_dir(repo, 7) / 'state.json'
        path.unlink(missing_ok=True)
        start.skip_file().unlink(missing_ok=True)
        if fields:
            state.state_update(repo, 7, **fields)

    with ExitStack() as stack:
        stack.enter_context(patch('lokay.start.load_repos', return_value=[
            {'name': repo, 'clone_path': str(clone), 'test': tests}]))
        stack.enter_context(patch('lokay.start.time.sleep', no_sleep))
        prepare = stack.enter_context(patch('lokay.start._prepare', side_effect=AssertionError('Plan/Build forbidden')))
        remote = stack.enter_context(patch('lokay.start.open_pr_for', return_value=pr))
        def git(path, args):
            assert path == worktree, (path, args)
            if args == ['branch', '--show-current']:
                return 0, 'lokay/7\n', ''
            if args == ['rev-parse', 'HEAD']:
                return 0, 'new\n', ''
            return 0, '', ''
        git_mock = stack.enter_context(patch('lokay.git._git', side_effect=git))
        reset()
        with patch('lokay.start._finish', return_value={'result': 'pending', 'sha': 'new'}) as finish:
            assert start.resume(picked) == {'result': 'pending', 'sha': 'new'}
            finish.assert_called_once_with(picked, worktree, 'lokay/7', 'new', tests)
        assert state.state_read(repo, 7)['sha'] == 'new'
        prepare.assert_not_called()

        # Reject unsafe worktrees before any Check, Fix, fetch or Merge.
        for kind in ('missing', 'branch', 'dirty', 'sha'):
            reset(node='fix', verdict={'result': 'fix', 'sha': 'old', 'uwagi': []})
            if kind == 'missing':
                worktree.rmdir()
            def unsafe_git(path, args):
                if kind == 'branch' and args == ['branch', '--show-current']:
                    return 0, 'user/branch', ''
                if kind == 'dirty' and args == ['status', '--porcelain']:
                    return 0, '?? user.txt', ''
                if kind == 'sha' and args == ['rev-parse', 'HEAD']:
                    return 0, 'old', ''
                return git(path, args)
            git_mock.side_effect = unsafe_git
            with patch('lokay.start._finish') as finish:
                result = start.resume(picked)
                assert result['result'] == 'needs_help', (kind, result)
                assert result['repo'] == repo and result['issue'] == 7
                assert result['pr'] == 12 and result['sha'] == 'new'
                assert kind in result['reason'], result
                finish.assert_not_called()
            assert not any(call.args[1][0] in ('fetch', 'merge', 'reset', 'worktree')
                           for call in git_mock.call_args_list), git_mock.call_args_list
            git_mock.reset_mock()
            assert state.state_read(repo, 7)['result'] == 'needs_help'
            assert 7 in start.load_skips(repo)
            if kind == 'missing':
                worktree.mkdir()
        git_mock.side_effect = git

        # A new PR SHA invalidates a saved Fix verdict, even without pick().
        reset(node='fix', sha='old', verdict={'result': 'fix', 'sha': 'old', 'uwagi': []})
        with patch('lokay.start._finish', return_value={'result': 'pr_open', 'sha': 'new'}):
            assert start.resume(picked)['result'] == 'pr_open'
        saved = state.state_read(repo, 7)
        assert saved['node'] == 'check' and saved['verdict'] is None, saved
        with patch('lokay.start._finish', return_value={'result': 'pending'}) as finish:
            start.resume(picked)
            finish.assert_called_once_with(picked, worktree, 'lokay/7', 'new', tests)

        # Exercise the real finishing graph with isolated external operations.
        diff_count = [0]
        def diff(*args, **kwargs):
            diff_count[0] += 1
            return SimpleNamespace(returncode=0, stdout=f'diff {diff_count[0]}', stderr='')
        stack.enter_context(patch('lokay.run.run_process', side_effect=diff))
        stack.enter_context(patch('lokay.gh.open_pr_for', return_value=pr))
        stack.enter_context(patch('lokay.gh.pr_checks', return_value={'result': 'green', 'failed': []}))
        stack.enter_context(patch('lokay.gh.check_comment', return_value={'result': 'done'}))
        stack.enter_context(patch('lokay.check.hunks', return_value=[]))
        stack.enter_context(patch('lokay.check.questions', return_value={'questions': []}))
        stack.enter_context(patch('lokay.decide.decide', return_value={}))
        stack.enter_context(patch('lokay.check.decide_hunks', return_value={'uwagi': []}))
        ci = stack.enter_context(patch('lokay.check.local_ci', side_effect=lambda sha, cmds, wt:
            {'result': 'green', 'sha': sha, 'failed': [], 'notes': [], 'log': 'ok'}))
        aggregate = stack.enter_context(patch('lokay.check.aggregate'))
        code = stack.enter_context(patch('lokay.fix.fix_code', return_value={'result': 'done'}))
        publish = stack.enter_context(patch('lokay.fix.fix_publish', return_value={'result': 'pushed', 'sha': 'new'}))
        merge = stack.enter_context(patch('lokay.merge.merge_sha', return_value={'result': 'merged', 'merge_sha': 'merged'}))
        finding = {'result': 'fix', 'sha': 'new', 'uwagi': [{'plik': 'a', 'pytanie': 'bug'}]}
        green = {'result': 'merge', 'sha': 'new', 'uwagi': []}

        for fixing in (False, True):
            reset(node='merge', sha='old', verdict={'result': 'merge', 'sha': 'old'})
            aggregate.reset_mock()
            aggregate.side_effect = [finding, green] if fixing else [green]
            ci.reset_mock(); code.reset_mock(); merge.reset_mock()
            result = start.resume(picked)
            assert result['result'] == 'merged', result
            assert code.call_count == int(fixing)
            assert aggregate.call_count == 1 + int(fixing)
            ci.assert_called_once_with('new', [tests], worktree)
            assert merge.call_count == 1
            args = merge.call_args.args
            assert args[:3] == (repo, 12, 'new') and args[3]['sha'] == 'new', args

        # Repeated findings cannot bypass the three-call Fix budget via Plan.
        for merge_after in (None, 1, 3):
            reset(node='check')
            aggregate.reset_mock(); code.reset_mock(); merge.reset_mock()
            checks = [0]
            def bounded_verdict(*args):
                checks[0] += 1
                assert checks[0] <= 4, 'Check/Fix loop exceeded its budget'
                if merge_after is not None and checks[0] > merge_after:
                    return {**green, 'evidence': {'extra': [1, 2]}}
                return finding
            aggregate.side_effect = bounded_verdict
            result = start.resume(picked)
            expected_fixes = 3 if merge_after is None else merge_after
            assert code.call_count == expected_fixes, (result, code.call_count)
            assert checks[0] == expected_fixes + 1
            if merge_after is None:
                assert result['result'] == 'needs_help', result
                assert state.state_read(repo, 7)['result'] == 'needs_help'
                merge.assert_not_called()
            else:
                assert result['result'] == 'merged', result
                merge.assert_called_once()
                assert merge.call_args.args[3] == {**green, 'evidence': {'extra': [1, 2]}}

        # main owns a real lock through Check, Fix and Merge, including failures.
        from lokay.lock import acquire, release as real_release
        for failure_at in (None, 'limit', 'check', 'fix', 'merge'):
            reset(node='check')
            held = acquire('example', repo)
            assert held['result'] == 'held'
            active = {**picked, 'held': held}
            check_calls = [0]
            def busy():
                assert acquire('example', repo)['result'] == 'busy'
            def checked(*args):
                busy()
                check_calls[0] += 1
                if failure_at == 'check':
                    raise RuntimeError('Check exception')
                return finding if failure_at == 'limit' or check_calls[0] == 1 else green
            def fixed(*args):
                busy()
                if failure_at == 'fix':
                    raise RuntimeError('Fix exception')
                return {'result': 'done'}
            def merged(*args, **kwargs):
                busy()
                assert args[3] is green, 'verdict must not be replaced'
                if failure_at == 'merge':
                    raise RuntimeError('Merge exception')
                return {'result': 'merged', 'merge_sha': 'new'}
            aggregate.side_effect = checked
            code.side_effect = fixed
            merge.side_effect = merged
            with patch('lokay.start.pick', return_value=active), \
                 patch('lokay.start.release', wraps=real_release) as release, redirect_stdout(io.StringIO()) as out:
                try:
                    start.main([])
                except RetryLoop:
                    raise AssertionError('a merge exception must end the run, not retry forever')
                else:
                    result = json.loads(out.getvalue().splitlines()[-1])
                    assert result['result'] == ( 'merged' if failure_at is None else
                                                'failed' if failure_at == 'check' else 'needs_help'), result
                release.assert_called_once_with(held)
            free = acquire('example', repo)
            assert free['result'] == 'held'
            real_release(free)
        code.side_effect = None; merge.side_effect = None

        # Each failing Fix node runs once; result and exception are separate cases.
        for node in ('fix_code', 'fix_publish'):
            for failure in ({'result': 'failed', 'reason': 'fixture failure'}, RuntimeError('fixture exception')):
                reset(node='fix', sha='new', pr=12, verdict=finding)
                code.reset_mock(); publish.reset_mock(); merge.reset_mock()
                code.side_effect = None; code.return_value = {'result': 'done'}
                publish.side_effect = None; publish.return_value = {'result': 'pushed', 'sha': 'new'}
                failing = code if node == 'fix_code' else publish
                if isinstance(failure, Exception):
                    failing.side_effect = failure
                else:
                    failing.return_value = failure
                result = start.resume(picked)
                assert result['result'] == 'needs_help' and node in result['reason'], result
                assert (result['repo'], result['issue'], result['pr'], result['sha']) == (repo, 7, 12, 'new')
                assert failing.call_count == 1
                merge.assert_not_called()
                assert state.state_read(repo, 7)['result'] == 'needs_help'
                assert 7 in start.load_skips(repo)
        code.side_effect = None; publish.side_effect = None
        # Publication during main synchronization must not loop either.
        for failure in ({'result': 'failed'}, RuntimeError('sync publish')):
            reset(node='check')
            publish.reset_mock(); merge.reset_mock()
            publish.side_effect = failure if isinstance(failure, Exception) else None
            publish.return_value = failure if isinstance(failure, dict) else None
            result = start.resume(picked)
            assert result['result'] == 'needs_help' and 'fix_publish' in result['reason'], result
            assert publish.call_count == 1
            merge.assert_not_called()

        # PR lookup failures do not fall back to Build or another PR.
        for missing in (None, {'number': 12}, RuntimeError('lookup')):
            reset()
            remote.side_effect = missing if isinstance(missing, Exception) else None
            remote.return_value = missing if not isinstance(missing, Exception) else None
            with patch('lokay.start._finish') as finish:
                result = start.resume(picked)
                assert result['result'] == 'needs_help', result
                finish.assert_not_called()
            prepare.assert_not_called()

        # main dispatch, final JSON and finally-release contracts.
        for node, target in [('check', 'resume'), ('fix', 'resume'), ('merge', 'resume'), ('plan', 'advance'), ('build', 'advance')]:
            with patch('lokay.start.pick', return_value={**picked, 'node': node}), \
                 patch('lokay.start.' + target, return_value={'result': 'needs_help'}) as step, \
                 patch('lokay.start.release') as release, redirect_stdout(io.StringIO()) as out:
                assert start.main([]) == 0
                step.assert_called_once()
                release.assert_called_once_with(picked['held'])
                assert json.loads(out.getvalue().splitlines()[-1]) == {'result': 'needs_help'}
        with patch('lokay.start.pick', return_value=picked), patch('lokay.start.resume', side_effect=RuntimeError('resume')), \
             patch('lokay.start.release') as release, redirect_stdout(io.StringIO()):
            try:
                start.main([])
            except RuntimeError:
                pass
            else:
                raise AssertionError('missing exception')
            release.assert_called_once_with(picked['held'])
        with patch('lokay.start.probes', return_value={'fixture': 'ok'}), patch('lokay.start.pick') as pick, redirect_stdout(io.StringIO()) as out:
            assert start.main(['--check']) == 0
            assert json.loads(out.getvalue()) == {'fixture': 'ok'}
            pick.assert_not_called()
        with patch('lokay.start.pick', return_value={'result': 'idle', 'reason': 'no_work'}), \
             patch('lokay.start.release') as release, redirect_stderr(io.StringIO()):
            assert start.main([]) == 0
            release.assert_not_called()
print('resume: identity, SHA invalidation, Check → Fix → Check → Merge, four Fix failures, JSON and release OK')
PY
