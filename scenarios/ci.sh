#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
uv run python - <<'PY'
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from lokay.check import aggregate, local_ci
from lokay.gh import pr_checks
from lokay.config import tick_budget

assert tick_budget({}) == 2700
assert tick_budget({'LOKAY_TICK_BUDGET': '0.25'}) == 0.25
for value in ('', '0', '-1', 'text', 'nan', 'inf', '-inf', '1e999', None, True, 30):
    try:
        tick_budget({'LOKAY_TICK_BUDGET': value})
    except ValueError as exc:
        assert str(exc) == 'LOKAY_TICK_BUDGET must be finite positive seconds'
    else:
        raise AssertionError(f'invalid tick budget accepted: {value!r}')

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / "code.py").write_text("def value(): return 42\n")
    (root / "verify.py").write_text("from code import value\nassert value() == 42\nprint('1 passed')\n")
    request = {"repo": "example/repo", "pr": 7, "sha": "head-a", "cwd": tmp,
               "test": [[sys.executable, "-B", "verify.py"]]}
    view = {"headRefOid": "head-a", "statusCheckRollup": [
        {"name": "verify", "status": "COMPLETED", "conclusion": "SUCCESS"}]}
    def gh(args):
        assert args[:3] == ["pr", "view", "7"]
        return 0, json.dumps(view), ""
    def check():
        ci = local_ci(request["sha"], request["test"], request["cwd"])
        with patch("lokay.gh._gh", gh):
            remote = pr_checks(request["repo"], request["pr"], request["sha"])
        if remote["result"] in ("pending", "sha_moved"):
            return {**ci, "result": remote["result"], "head_sha": remote["sha"]}
        ci["failed"].extend({"warstwa": "GitHub CI", "plik": "", "log": name}
                            for name in remote.get("failed") or [])
        ci["result"] = "red" if ci["failed"] else "green"
        return ci

    assert check()["result"] == "green"
    # The PR mutation must be rejected even when GitHub and the model approve it.
    (root / "code.py").write_text("def value(): return 0\n")
    request["sha"] = view["headRefOid"] = "head-b"
    red = check()
    assert red["result"] == "red" and not red["failed"][0]["flaky"], red
    assert aggregate("head-b", red, [{"next": "ok"}])["result"] == "fix"
    (root / "code.py").write_text("def value(): return 42\n")
    (root / "verify.py").write_text(
        "from pathlib import Path\nfrom code import value\n"
        "p = Path('attempt')\nfirst = not p.exists()\np.touch()\n"
        "assert not first, 'transient failure'\nassert value() == 42\nprint('1 passed')\n")
    flaky = check()
    assert flaky["result"] == "green" and flaky["notes"][0]["flaky"], flaky
    verdict = aggregate("head-b", flaky, [{"next": "issue", "uwagi": [{"pytanie": "correctness"}]}])
    assert not any(row.get("flaky") for row in verdict["uwagi"]), verdict
    assert any(row.get("flaky") for row in verdict['notes']), verdict
    view["statusCheckRollup"] = [{"context": "legacy", "state": "PENDING"}]
    pending = check()
    assert pending["result"] == "pending", pending
    assert aggregate("head-b", pending, [])['result'] == "check"
    view["statusCheckRollup"] = [{"context": "legacy", "state": "FAILURE"}]
    assert check()["result"] == "red"
    view["statusCheckRollup"] = [{"name": "verify", "status": "IN_PROGRESS", "conclusion": None}]
    assert check()["result"] == "pending"
    view["headRefOid"] = "head-c"
    moved = check()
    assert moved["result"] == "sha_moved" and moved["head_sha"] == "head-c", moved
    view["headRefOid"] = "head-b"
    request["test"] = []
    view["statusCheckRollup"] = []
    assert check()["result"] == "green"
    with patch('lokay.gh._gh', gh):
        assert pr_checks(request['repo'], 7, 'head-b')['result'] == 'no_ci'
    timed_out = local_ci('timeout', [[sys.executable, '-c', 'import time; time.sleep(2)']], root, timeout=0.01)
    assert timed_out['result'] == 'red' and timed_out['failed'], timed_out
    unavailable = local_ci('missing', [[str(root / 'missing-command')]], root)
    assert unavailable['result'] == 'red' and unavailable['failed'], unavailable
    no_tests = local_ci('empty', [], root)
    assert no_tests['result'] == 'green' and no_tests['notes'][0]['log'] == 'no tests configured', no_tests
    assert aggregate('empty', no_tests, [{'next': 'ok'}])['result'] == 'merge'

# Resume the production Check path. Pending remote CI stops after local CI has
# been persisted, without replacing the cache condition or invoking Fix.
import os
from contextlib import ExitStack
from subprocess import CompletedProcess
from lokay import start, state
from lokay.run import run_process

with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
    root = Path(tmp)
    clone = root / 'clone'
    worktree = root / 'clone-wt-1'
    clone.mkdir()
    worktree.mkdir()
    config = root / 'repos.yaml'
    attempts = worktree / 'attempts'
    (worktree / 'verify.py').write_text(
        "import sys\nfrom pathlib import Path\n"
        "with Path('attempts').open('a') as f: f.write(sys.argv[1] + '\\n')\n"
        "print('result=' + sys.argv[1])\nprint('1 passed')\nsys.exit(int(sys.argv[1]))\n")
    stack.enter_context(patch.dict(os.environ, LOKAY2_REPOS_FILE=str(config)))
    stack.enter_context(patch('lokay.state.RUNS', root / 'runs'))
    head = {'sha': 'same-head'}
    def git(path, args):
        if args == ['branch', '--show-current']:
            return 0, 'lokay/1', ''
        if args == ['rev-parse', 'HEAD']:
            return 0, head['sha'], ''
        return 0, '', ''
    stack.enter_context(patch('lokay.git._git', git))
    stack.enter_context(patch('lokay.build.tidy_and_commit', return_value=([], [])))
    stack.enter_context(patch('lokay.start.refresh_body', return_value={'result': 'updated'}))
    def pr(*args):
        return {'number': 7, 'headRefName': 'lokay/1', 'headRefOid': head['sha']}
    stack.enter_context(patch('lokay.gh.open_pr_for', pr))
    stack.enter_context(patch('lokay.start.open_pr_for', pr))
    stack.enter_context(patch('lokay.fix.fix_publish', side_effect=lambda *a:
        {'result': 'pushed', 'sha': head['sha']}))
    stack.enter_context(patch('lokay.gh.pr_checks', return_value={'result': 'pending'}))
    comment = stack.enter_context(patch('lokay.gh.check_comment'))
    def issue_view(args):
        assert args == ['issue', 'view', '1', '--repo', 'example/resume', '--json', 'title,body'], args
        return 0, json.dumps({'title': 'Fix code', 'body': ''}), ''
    issue = Mock(side_effect=issue_view)
    # start also holds an imported reference; keep both API entry points isolated.
    stack.enter_context(patch('lokay.gh._gh', issue))
    stack.enter_context(patch('lokay.start._gh', issue))
    # Guard behavior has its own real-Git scenario; this fixture has no Git repository.
    guard = stack.enter_context(patch('lokay.merge_guard.merge_guard', return_value={
        'removed': [], 'reset': []}))
    package_diff = False
    package = worktree / 'packages' / 'argus'
    package.mkdir(parents=True)
    (package / 'pyproject.toml').touch()
    def processes(argv, **kwargs):
        if argv == ['git', 'diff', 'origin/main...HEAD'] and package_diff:
            return CompletedProcess(argv, 0, 'diff --git a/packages/argus/code.py b/packages/argus/code.py\n'
                '--- a/packages/argus/code.py\n+++ b/packages/argus/code.py\n@@ -1 +1 @@\n-old\n+new\n', '')
        if argv in (['git', 'diff', 'origin/main...HEAD'], ['git', 'diff', '--stat', 'origin/main...HEAD']):
            return CompletedProcess(argv, 0, '', '')
        return run_process(argv, **kwargs)
    stack.enter_context(patch('lokay.run.run_process', processes))
    picked = {'repo': 'example/resume', 'issue': 1, 'node': 'check'}
    state.state_update(picked['repo'], 1, node='check')
    def configure(exit_code):
        argv = [sys.executable, '-B', 'verify.py', str(exit_code)]
        config.write_text('repos:\n  - name: example/resume\n'
                          f'    clone_path: {clone}\n    test: {json.dumps(argv)}\n    merge: on\n')
        return argv
    def resume():
        assert start.resume.__wrapped__(picked)['result'] == 'pending'
        return state.state_read(picked['repo'], 1)['local_ci']
    old_argv = configure(1)
    red = resume()
    assert red['result'] == 'red' and attempts.read_text().splitlines() == ['1', '1']
    new_argv = configure(0)
    green = resume()
    assert green['result'] == 'green', 'changed argv reused stale red CI on the same SHA'
    assert green['sha'] == red['sha'] == head['sha']
    assert green['argv'] == new_argv and 'result=0' in green['log'], green
    assert attempts.read_text().splitlines() == ['1', '1', '0']
    assert resume() == green
    assert attempts.read_text().splitlines() == ['1', '1', '0', '0'], 'same SHA/argv reused CI from a previous run'
    head['sha'] = 'new-head'
    assert resume()['sha'] == 'new-head'
    assert attempts.read_text().splitlines() == ['1', '1', '0', '0', '0']
    legacy = state.state_read(picked['repo'], 1)['local_ci']
    del legacy['argv']
    state.state_update(picked['repo'], 1, local_ci=legacy)
    assert resume()['argv'] == new_argv
    assert attempts.read_text().splitlines() == ['1', '1', '0', '0', '0', '0']
    configure(2)
    failed = resume()
    assert failed['result'] == 'red' and 'result=2' in failed['log'], failed
    assert attempts.read_text().splitlines()[-2:] == ['2', '2']
    history = state.run_dir(picked['repo'], 1) / 'rounds.md'
    assert history.read_text().count('GitHub CI pending') == 6
    # Use the real Check verdict and model response parser; only external effects are faked.
    stack.enter_context(patch('lokay.gh.pr_checks', return_value={'result': 'no_ci', 'failed': [],
        'notes': [{'warstwa': 'GitHub CI', 'log': 'no GitHub checks configured'}]}))
    merge = stack.enter_context(patch('lokay.merge.merge_sha', return_value={
        'result': 'merged', 'merge_sha': 'merged'}))
    fix = stack.enter_context(patch('lokay.fix.fix_code', return_value={'result': 'failed'}))
    stack.enter_context(patch('lokay.start._retry', side_effect=lambda picked, node, action, *args: action()))
    kinds = 'correctness alignment architecture security production scope tests'
    from lokay.check import lens
    for choice, exit_code, package_diff in (('ok', 0, False), ('issue', 0, False),
            ('ok', 1, False), ('ok', None, False), ('ok', 0, True), ('ok', None, True)):
        argv = configure(exit_code or 0)
        if exit_code is None:
            argv = []
            config.write_text('repos:\n  - name: example/resume\n'
                             f'    clone_path: {clone}\n    test: []\n    merge: on\n')
        cached = ({'sha': head['sha'], 'argv': [], 'result': 'green',
                   'failed': [], 'notes': [], 'log': ''} if exit_code is None else None)
        state.state_update(picked['repo'], 1, node='check', verdict=None, local_ci=cached,
                           issue_title='fixture', issue_body='')
        merge.reset_mock(); fix.reset_mock()
        calls = []
        def model(request):
            calls.append(request)
            assert request['state']['kind'] in kinds.split(), request
            if request['questions'][0]['id'] == 'where':
                return {q['id']: {'choice': 'none' if q['id'] == 'where' else 'logic bug',
                    'probabilities': {key: (1.0 if key == ('none' if q['id'] == 'where' else 'logic bug') else 0.0)
                                      for key in q['options']}}
                        for q in request['questions']}
            if package_diff:
                return {q['id']: {'choice': 'ok' if q['id'] == 'next' else 'false',
                    'probabilities': {key: (1.0 if key == ('ok' if q['id'] == 'next' else 'false') else 0.0)
                                      for key in q['options']}} for q in request['questions']}
            assert len(request['questions']) == 1, request
            assert lens(request['state']['kind']) in request['questions'][0]['instructions']
            return {'next': {'choice': choice, 'probabilities': {
                choice: 0.9, ('issue' if choice == 'ok' else 'ok'): 0.1}}}
        with patch('lokay.decide.decide', side_effect=model), \
             patch('lokay.start._prepare', return_value={'result': 'fixture-plan'}) as prepare:
            result = start.resume.__wrapped__(picked)
        assert len(calls) == (14 if choice == 'issue' else 7), calls
        if choice == 'issue':
            assert result['result'] == 'fixture-plan', result
            prepare.assert_called_once()
            merge.assert_not_called()
            fix.assert_not_called()
        elif exit_code is None or (exit_code == 0 and not package_diff):
            assert result['result'] == 'merged', result
            merge.assert_called_once()
            guard.assert_called()
            issue.assert_not_called()  # Saved issue metadata must not be fetched again.
            fix.assert_not_called()
            saved = state.state_read(picked['repo'], 1)
            assert saved['ci'] == 'no_ci' and saved['tested'] == (exit_code == 0), saved
            assert comment.call_args.args[-1]['tested'] == (exit_code == 0)
        else:
            assert result['result'] == 'failed', result
            merge.assert_not_called()
            fix.assert_called_once()
            if package_diff:
                assert any('changed package' in row.get('log', '') for row in
                           state.state_read(picked['repo'], 1)['verdict']['uwagi'])
print('CI: mutation, timeout, flaky, remote guards, SHA/argv cache; 4 real Check → merge cases OK')
PY
