#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
uv run --offline python - <<'PY'
import tempfile
from pathlib import Path
from lokay.build import _git
from lokay.check import aggregate
from lokay.scope import code_scope_issue
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    _git(root, ['init', '-b', 'main'])
    _git(root, ['config', 'user.name', 'fixture'])
    _git(root, ['config', 'user.email', 'fixture@example.test'])
    (root / 'code.py').write_text('old\n')
    _git(root, ['add', '.']); _git(root, ['commit', '-m', 'base'])
    _git(root, ['update-ref', 'refs/remotes/origin/main', 'HEAD'])
    (root / 'plan.md').write_text('plan\n')
    (root / 'scripts').mkdir()
    (root / 'scripts/x.py').write_text('print("report")\n')
    _git(root, ['add', '.']); _git(root, ['commit', '-m', 'plan'])
    files = _git(root, ['diff', '--name-only', 'origin/main...HEAD']).splitlines()
    scope = code_scope_issue(files, '## Pliki\n- `code.py`\n- `plan.md`\n## Testy\n')
    assert scope and scope['warstwa'] == 'scope'
with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as runs:
    root = Path(tmp)
    _git(root, ['init', '-b', 'main'])
    _git(root, ['config', 'user.name', 'fixture'])
    _git(root, ['config', 'user.email', 'fixture@example.test'])
    (root / 'code.py').write_text('old\n')
    _git(root, ['add', '.']); _git(root, ['commit', '-m', 'base'])
    _git(root, ['update-ref', 'refs/remotes/origin/main', 'HEAD'])
    (root / 'plan.md').write_text('plan\n')
    _git(root, ['add', '.']); _git(root, ['commit', '-m', 'plan'])
    files = _git(root, ['diff', '--name-only', 'origin/main...HEAD']).splitlines()
    plan = '## Cel\nDodaj obsługę X. Opis tylko tutaj.\n## Pliki\n- `code.py`\n- `plan.md`\n## Testy\nnone\n'
    assert code_scope_issue(files, plan)
    assert code_scope_issue(['tests/test_a.py'], plan)
    assert code_scope_issue(['code.py', 'plan.md'], plan) is None
    assert code_scope_issue(['code.py', 'scripts/x.py'], plan)
    assert code_scope_issue(['code.py', 'extra.md'], plan)
    assert code_scope_issue(['code.py', 'tests/test_a.py', 'uv.lock', 'package-lock.json'], plan) is None
    assert code_scope_issue(['plan.md'], '## Pliki\nplan.md\n## Testy\n') is None
    assert code_scope_issue(['code.py'], '## Pliki\ncode.py — implement\n## Testy\n') is None
    verdict = aggregate('sha', {'sha': 'sha', 'result': 'green'}, [{'next': 'ok'}])
    scope = code_scope_issue(files, plan)
    if scope:
        verdict = {**verdict, 'result': 'fix', 'uwagi': [scope]}
    assert verdict['result'] == 'fix' and verdict['uwagi'][0]['warstwa'] == 'scope'
    # Real Check graph: main advances, merges before CI, then a green model
    # cannot merge the docs-only PR. Fix adds production code before Merge.
    import os
    from contextlib import ExitStack
    from subprocess import CompletedProcess
    from unittest.mock import patch
    from lokay import start, state
    from lokay.git import _git as real_git
    head = {'sha': _git(root, ['rev-parse', 'HEAD'])}
    pr_head = head['sha']
    _git(root, ['checkout', '-b', 'upstream', 'origin/main'])
    (root / 'upstream.py').write_text('new main\n')
    _git(root, ['add', '.']); _git(root, ['commit', '-m', 'main advance'])
    _git(root, ['update-ref', 'refs/remotes/origin/main', 'HEAD'])
    main_sha = _git(root, ['rev-parse', 'HEAD'])
    _git(root, ['checkout', 'main'])
    repo = {'name': 'example/repo', 'clone_path': str(root), 'test': [], 'setup': []}
    picked = {'repo': repo['name'], 'issue': 1, 'node': 'check'}
    events = []
    def git(path, args):
        if args[0] == 'fetch':
            return 0, '', ''
        return real_git(path, args)
    def publish(*args):
        head['sha'] = _git(root, ['rev-parse', 'HEAD'])
        return {'result': 'pushed', 'sha': head['sha']}
    def ci(sha, commands, cwd):
        events.append('ci')
        assert _git(root, ['merge-base', '--is-ancestor', main_sha, 'HEAD']) == ''
        assert sha != pr_head, 'CI ran on stale PR base'
        return {'result': 'green', 'sha': sha, 'failed': [], 'notes': [], 'log': ''}
    def fix(*args, **kwargs):
        events.append('fix')
        assert state.state_read(repo['name'], 1)['verdict']['uwagi'][-1]['warstwa'] == 'scope'
        if events.count('fix') == 1:
            (root / 'code.py').write_text('implemented\n')
            (root / 'outside.py').write_text('unplanned\n')
        else:
            assert 'outside.py' in state.state_read(repo['name'], 1)['verdict']['uwagi'][-1]['log']
            (root / 'outside.py').unlink()
        _git(root, ['add', '.']); _git(root, ['commit', '-m', 'production'])
        return {'result': 'done', 'artifact': _git(root, ['rev-parse', 'HEAD'])}
    def merge(*args, **kwargs):
        events.append('merge')
        assert events.count('fix') == 2, 'out-of-scope PR reached Merge'
        return {'result': 'merged', 'merge_sha': head['sha']}
    with ExitStack() as stack:
        stack.enter_context(patch('lokay.state.RUNS', Path(runs)))
        stack.enter_context(patch('lokay.start.load_repos', return_value=[repo]))
        stack.enter_context(patch('lokay.start.refresh_body', return_value={'result': 'updated'}))
        stack.enter_context(patch('lokay.git._git', side_effect=git))
        stack.enter_context(patch('lokay.merge_guard._git', side_effect=lambda path, args:
                                  '' if args[0] == 'fetch' else _git(path, args)))
        stack.enter_context(patch('lokay.fix.fix_publish', side_effect=publish))
        stack.enter_context(patch('lokay.fix.fix_code', side_effect=fix))
        stack.enter_context(patch('lokay.check.local_ci', side_effect=ci))
        stack.enter_context(patch('lokay.gh.open_pr_for', side_effect=lambda *a: {'number': 1, 'headRefOid': head['sha']}))
        stack.enter_context(patch('lokay.start.open_pr_for', side_effect=lambda *a: {'number': 1, 'headRefOid': head['sha']}))
        stack.enter_context(patch('lokay.gh.pr_checks', return_value={'result': 'green', 'failed': []}))
        stack.enter_context(patch('lokay.gh.check_comment'))
        stack.enter_context(patch('lokay.merge.merge_sha', side_effect=merge))
        stack.enter_context(patch('lokay.decide.decide', side_effect=lambda request: {
            q['id']: {'choice': 'ok' if q['id'] == 'next' else 'false',
                      'probabilities': {'ok': 1.0, 'issue': 0.0} if q['id'] == 'next' else {'true': 0.0, 'false': 1.0}}
            for q in request['questions']}))
        state.state_update(repo['name'], 1, node='check', issue_title='Dodaj obsługę X', issue_body='opis tylko')
        (state.run_dir(repo['name'], 1) / 'plan.md').write_text(plan)
        result = start._finish(picked, root, 'main', pr_head, [])
        assert result['result'] == 'merged' and events == ['ci', 'fix', 'ci', 'fix', 'ci', 'merge'], (result, events)
        rounds = (state.run_dir(repo['name'], 1) / 'rounds.md').read_text()
        assert 'Check scope: Diff does not touch any planned code file: code.py' in rounds
        assert 'Check scope: Diff contains files outside ## Pliki: outside.py' in rounds
print('docs_only_fix: scope gate in real Check graph; advanced main merged before CI; Fix → Merge OK')
PY
