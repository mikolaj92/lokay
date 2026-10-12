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

    # Backoff grows once per failed tick, caps at one hour, and never writes skips.
    for failures in (0, 1, 6, 7, 20):
        reset(node='fix', failures=failures, plan_prompt='original prompt',
              plan_evaluations=3, plan_accepted_sha='accepted')
        reason = 'fix_code: no changes'
        with patch('lokay.start.time.time', return_value=1000):
            @start.guarded_step
            def failed_tick(active):
                return start.needs_help(active, reason, 'new')
            assert failed_tick(picked) == {'result': 'failed', 'reason': reason}
        saved = state.state_read(repo, 7)
        assert saved['failures'] == failures + 1, saved
        assert saved['retry_at'] == 1000 + min(3600, 60 * 2 ** min(failures, 6)), saved
        assert saved['node'] == 'plan' and saved['plan_phase'] == 'write'
        assert saved['plan_prompt'].startswith('original prompt') and reason in saved['plan_prompt']
        assert saved['plan_evaluations'] == 0 and saved['plan_accepted_sha'] is None
        assert not start.skip_file().exists()

    with ExitStack() as stack:
        stack.enter_context(patch('lokay.start.load_repos', return_value=[
            {'name': repo, 'clone_path': str(clone), 'test': tests}]))
        stack.enter_context(patch('lokay.start.time.sleep', no_sleep))
        tidy = stack.enter_context(patch('lokay.build.tidy_and_commit', return_value=([], [])))
        refresh = stack.enter_context(patch('lokay.start.refresh_body', return_value={'result': 'updated'}))
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
        git_mock.reset_mock()
        for kind in ('missing', 'branch'):
            reset(node='fix', verdict={'result': 'fix', 'sha': 'old', 'uwagi': []})
            if kind == 'missing':
                worktree.rmdir()
            def unsafe_git(path, args):
                if kind == 'branch' and args == ['branch', '--show-current']:
                    return 0, 'user/branch', ''
                return git(path, args)
            git_mock.side_effect = unsafe_git
            with patch('lokay.start._finish') as finish:
                result = start.resume(picked)
                assert result['result'] == 'failed', (kind, result)
                saved = state.state_read(repo, 7)
                assert saved['pr'] == 12 and saved['sha'] == 'new'
                assert kind in result['reason'], result
                finish.assert_not_called()
            assert not any(call.args[1][0] in ('fetch', 'merge', 'reset', 'worktree')
                           for call in git_mock.call_args_list), git_mock.call_args_list
            git_mock.reset_mock()
            saved = state.state_read(repo, 7)
            assert saved['result'] == 'failed' and saved['node'] == 'check'
            assert saved['failures'] == 1 and saved['retry_at'] > start.time.time()
            assert 7 not in start.load_skips(repo)
            if kind == 'missing':
                worktree.mkdir()
        git_mock.side_effect = git

        # Dirty changes are committed and published before Check.
        reset()
        tidy.return_value = (['user.txt'], ['uv.lock'])
        def tidied_git(path, args):
            if args == ['rev-parse', 'HEAD']:
                return 0, 'tidied', ''
            return git(path, args)
        git_mock.side_effect = tidied_git
        remote.side_effect = [pr, {'number': 12, 'headRefOid': 'tidied'}]
        with patch('lokay.fix.fix_publish', return_value={'result': 'pushed', 'sha': 'tidied'}) as publish, \
             patch('lokay.start._finish', return_value={'result': 'pending'}) as finish:
            assert start.resume(picked)['result'] == 'pending'
            publish.assert_called_once_with(worktree, 'lokay/7', 'new')
            finish.assert_called_once_with(picked, worktree, 'lokay/7', 'tidied', tests)
        tidy.return_value = ([], [])
        git_mock.side_effect = git
        remote.side_effect = None

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
        stack.enter_context(patch('lokay.check.decide_batches', return_value={'next': 'ok', 'uwagi': []}))
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

        # Repeated findings return through Plan instead of imposing a Fix cap.
        reset(node='check', issue_title='title', issue_body='body')
        aggregate.side_effect = [finding, finding, green]
        code.reset_mock(); prepare.reset_mock()
        with patch('lokay.start._prepare', return_value=(worktree, 'lokay/7', 'new', tests, 2)) as replan:
            assert start.resume(picked)['result'] == 'merged'
            replan.assert_called_once()
        assert code.call_count == 1
        saved = state.state_read(repo, 7)
        assert 'Fix made no progress' in saved['plan_prompt']
        assert 'Uwagi:' in saved['plan_prompt'] and 'Rounds:' in saved['plan_prompt']
        assert 'Fix → Plan: no progress, findings=' in (state.run_dir(repo, 7) / 'rounds.md').read_text()

        # Distinct findings can require more than three Fix calls.
        for merge_after in (1, 3, 5):
            reset(node='check')
            aggregate.reset_mock(); code.reset_mock(); merge.reset_mock()
            checks = [0]
            def bounded_verdict(*args):
                checks[0] += 1
                assert checks[0] <= merge_after + 1, 'unexpected extra Check'
                if checks[0] > merge_after:
                    return {**green, 'evidence': {'extra': [1, 2]}}
                return {**finding, 'uwagi': [{'plik': 'a', 'pytanie': f'bug {checks[0]}'}]}
            aggregate.side_effect = bounded_verdict
            result = start.resume(picked)
            expected_fixes = merge_after
            assert code.call_count == expected_fixes, (result, code.call_count)
            assert checks[0] == expected_fixes + 1
            assert result['result'] == 'merged', result
            merge.assert_called_once()
            assert merge.call_args.args[3] == {**green, 'evidence': {'extra': [1, 2]}}

        # main owns a real lock through Check, Fix and Merge, including failures.
        from lokay.lock import acquire, release as real_release
        for failure_at in (None, 'check', 'fix', 'merge'):
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
                return finding if check_calls[0] == 1 else green
            def fixed(*args, **kwargs):
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
                    assert result['result'] == ('merged' if failure_at is None else 'failed'), result
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
                assert result['result'] == 'failed' and node in result['reason'], result
                saved = state.state_read(repo, 7)
                assert (saved['pr'], saved['sha']) == (12, 'new')
                assert failing.call_count == 1
                merge.assert_not_called()
                assert saved['result'] == 'failed' and saved['failures'] == 1, saved
                assert saved['retry_at'] > start.time.time()
                assert saved['node'] == ('plan' if node == 'fix_code' else 'check'), saved
                if node == 'fix_code':
                    assert saved['plan_phase'] == 'write' and saved['plan_evaluations'] == 0
                    assert saved['plan_accepted_sha'] is None
                    assert result['reason'] in saved['plan_prompt']
                assert result['reason'] + ' → retry later' in (state.run_dir(repo, 7) / 'rounds.md').read_text()
                assert 7 not in start.load_skips(repo)
        code.side_effect = None; publish.side_effect = None
        # Publication during main synchronization must not loop either.
        for failure in ({'result': 'failed'}, RuntimeError('sync publish')):
            reset(node='check')
            publish.reset_mock(); merge.reset_mock()
            publish.side_effect = failure if isinstance(failure, Exception) else None
            publish.return_value = failure if isinstance(failure, dict) else None
            result = start.resume(picked)
            assert result['result'] == 'failed' and 'fix_publish' in result['reason'], result
            assert publish.call_count == 1
            merge.assert_not_called()

        # PR lookup failures do not fall back to Build or another PR.
        for missing in (None, {'number': 12}, RuntimeError('lookup')):
            reset()
            remote.side_effect = missing if isinstance(missing, Exception) else None
            remote.return_value = missing if not isinstance(missing, Exception) else None
            with patch('lokay.start._finish') as finish:
                result = start.resume(picked)
                assert result['result'] == 'failed', result
                finish.assert_not_called()
            prepare.assert_not_called()

        # CLI refresh bypasses pick().
        from lokay.cli import main as cli_main
        refresh.reset_mock()
        with patch('lokay.start.pick') as pick, redirect_stdout(io.StringIO()) as out:
            assert cli_main(['refresh-body', repo, '7']) == 0
            refresh.assert_called_once_with(repo, 7)
            pick.assert_not_called()
            assert json.loads(out.getvalue()) == {'result': 'updated'}

        # main dispatch, final JSON and finally-release contracts.
        for node, target in [('check', 'resume'), ('fix', 'resume'), ('merge', 'resume'), ('plan', 'advance'), ('build', 'advance')]:
            with patch('lokay.start.pick', return_value={**picked, 'node': node}), \
                 patch('lokay.start.' + target, return_value={'result': 'failed'}) as step, \
                 patch('lokay.start.release') as release, redirect_stdout(io.StringIO()) as out:
                assert start.main([]) == 0
                step.assert_called_once()
                release.assert_called_once_with(picked['held'])
                assert json.loads(out.getvalue().splitlines()[-1]) == {'result': 'failed'}
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
