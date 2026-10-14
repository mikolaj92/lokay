#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
uv run python - <<'PY'
import json
import os
from lokay.check import aggregate, decide_batches
from lokay.decide import to_wire

os.environ['LOKAY2_DECISION_API'] = 'mini'
rows = [{'plik': 'a.py', 'linia_od': 10, 'linia_do': 12}]

def run(chosen, probability=.9, files=rows, distribution=None, kind='correctness'):
    calls = []
    def decide(request):
        calls.append(request)
        assert len(json.dumps(to_wire('mini', '', request))) < 5500
        answers = {}
        for question in request['questions']:
            options = list(question['options'])
            choice = {'next': 'issue', 'where': chosen, 'change': 'logic bug'}.get(question['id'], 'false')
            p = probability if question['id'] == 'where' else .9
            probabilities = {key: p if key == choice else (1-p)/(len(options)-1) for key in options}
            if question['id'] == 'where' and distribution is not None:
                probabilities = distribution
            answers[question['id']] = {'choice': choice, 'probabilities': probabilities, 'confidence': p}
        return answers
    result = decide_batches(kind, files, {'sha': 'abc', 'repo': 'example/repo', 'issue': 1}, decide)
    return result, calls

concrete, calls = run('a.py:10-12')
assert len(calls) == 2
assert concrete['uwagi'] == [{'plik': 'a.py', 'linia_od': 10, 'linia_do': 12,
                             'pytanie': 'correctness', 'p': .9, 'zmiana': 'logic bug'}]
assert aggregate('abc', {'sha': 'abc', 'result': 'green'}, [concrete])['result'] == 'fix'
noted, calls = run('none')
assert len(calls) == 2 and not noted['uwagi']
assert noted['replan'][0]['prompt'] == 'lens correctness widzi problem w a.py, wskaż konkret'
green = aggregate('abc', {'sha': 'abc', 'result': 'green'}, [noted])
assert green['result'] == 'plan' and green['replan'] == noted['replan']
red = aggregate('abc', {'sha': 'abc', 'result': 'red', 'failed': [{'warstwa': 'CI'}]}, [noted])
assert red['result'] == 'fix' and red['uwagi'] == [{'warstwa': 'CI'}]
from unittest.mock import patch
from lokay.check import THRESHOLD
assert THRESHOLD == .85
files = rows + [{'plik': 'b.py', 'linia_od': 1, 'linia_do': 2}]
with patch('lokay.state.rounds_append') as log:
    edge, _ = run('a.py:10-12', files=files,
                  distribution={'a.py:10-12': .5, 'b.py:1-2': .25, 'none': .25})
    assert edge['uwagi']
    text = log.call_args.args[2]
    assert 'correctness' in text and 'chosen=a.py:10-12, p=0.5, none=0.25' in text
    assert 'top-3=[["a.py:10-12", 0.5], ["b.py:1-2", 0.25], ["none", 0.25]]' in text
    assert 'change=logic bug, change_p=0.9' in text
with patch('lokay.state.rounds_append') as log:
    for kind in 'correctness alignment architecture security production scope tests'.split():
        run('none', kind=kind)
    assert log.call_count == 7
    for call, kind in zip(log.call_args_list, 'correctness alignment architecture security production scope tests'.split()):
        assert f'Check follow-up {kind}:' in call.args[2]
for distribution in (
    {'a.py:10-12': .3, 'b.py:1-2': .5, 'none': .2},
    {'a.py:10-12': .5, 'b.py:1-2': .24, 'none': .26},
):
    low, _ = run(max(distribution, key=distribution.get), files=files, distribution=distribution)
    if distribution['none'] == .26:
        assert not low['uwagi'] and low['replan']
accepted, _ = run('a.py:10-12', files=files,
                  distribution={'a.py:10-12': .49941, 'b.py:1-2': .30934, 'none': .19125})
assert accepted['uwagi']
accepted, _ = run('a.py:10-12', .7)
assert accepted['uwagi']
# Malformed choice must never accept a non-argmax finding.
try:
    low, _ = run('a.py:10-12', files=files,
                 distribution={'a.py:10-12': .2, 'b.py:1-2': .7, 'none': .1})
except Exception as exc:
    from lokay.decide import DecisionError
    assert isinstance(exc, DecisionError)
else:
    assert not low['uwagi']
many = [{'plik': f'file-{n:03d}-' + 'x'*100 + '.py', 'linia_od': 1, 'linia_do': 2} for n in range(100)]
noted, calls = run('none', files=many)
assert sum(any(q['id'] == 'where' for q in call['questions']) for call in calls) > 1
assert len(noted['replan']) == 1
from pathlib import Path
from unittest.mock import patch
from lokay.gh import check_comment
from lokay import start
refresh_body = start.refresh_body
with patch('lokay.gh._gh', return_value=(0, 'url', '')) as gh:
    check_comment('example/repo', 1, 1, green, {'result': 'green'})
    body = gh.call_args.args[0][-1]
    assert 'plan' in body
with patch('lokay.start.load_repos', return_value=[{'name': 'example/repo', 'clone_path': '/tmp/clone'}]), \
     patch('lokay.start.open_pr_for', return_value={'number': 1}), \
     patch('lokay.start.state_read', return_value={'verdict': green}), \
     patch('lokay.build.pr_body', return_value='base'), \
     patch('lokay.gh.pr_set_body', return_value={'result': 'updated'}) as update:
    start.refresh_body('example/repo', 1)
    assert update.called

with patch('lokay.start.load_repos', return_value=[{'name': 'example/repo', 'clone_path': '/tmp/clone'}]), \
     patch('lokay.start.state_read', return_value={'node': 'fix', 'verdict': {'result': 'fix', 'sha': 'abc', 'uwagi': []}}), \
     patch('lokay.start.state_update') as update, \
     patch('lokay.git._git', return_value=(0, 'abc', '')), \
     patch('lokay.run.run_process', return_value=__import__('subprocess').CompletedProcess([], 0, '', '')), \
     patch('lokay.fix.fix_code') as fix:
    assert start._finish({'repo': 'example/repo', 'issue': 1}, Path('/tmp/worktree'), 'lokay/1', 'abc', []) == {'result': 'check', 'sha': 'abc'}
    assert update.call_args.kwargs['node'] == 'check'
    assert update.call_args.kwargs['verdict'] is None and update.call_args.kwargs['local_ci'] is None
    fix.assert_not_called()
# A fresh Check run writes seven independent lens results, then replans without merging.
import tempfile
from contextlib import ExitStack
from subprocess import CompletedProcess
from lokay import state
from lokay.check import QUESTIONS
with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
    stack.enter_context(patch('lokay.state.RUNS', Path(tmp) / 'runs'))
    stack.enter_context(patch('lokay.observe.current'))
    picked = {'repo': 'example/repo', 'issue': 1809}
    state.state_update(picked['repo'], picked['issue'], node='check', issue_title='Fix bug', issue_body='')
    stack.enter_context(patch('lokay.start.load_repos', return_value=[{'name': picked['repo'], 'clone_path': tmp}]))
    stack.enter_context(patch('lokay.git._git', side_effect=lambda path, args:
        (0, 'abc' if args[0] == 'rev-parse' else '', '')))
    stack.enter_context(patch('lokay.run.run_process', return_value=CompletedProcess([], 0,
        'diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -10,1 +10,1 @@\n-old\n+new\n', '')))
    stack.enter_context(patch('lokay.fix.fix_publish', return_value={'result': 'pushed', 'sha': 'abc'}))
    stack.enter_context(patch('lokay.start.pushed_pr', return_value={'number': 1}))
    stack.enter_context(patch('lokay.start.refresh_body', return_value={'result': 'updated'}))
    stack.enter_context(patch('lokay.gh.open_pr_for', return_value={'number': 1}))
    stack.enter_context(patch('lokay.gh.pr_checks', return_value={'result': 'green'}))
    stack.enter_context(patch('lokay.check.local_ci', side_effect=lambda sha, commands, cwd: {
        'sha': sha, 'result': 'green', 'tested': True, 'tested_cwds': [str(cwd.resolve())],
        'failed': [], 'notes': [], 'log': '1 passed'}))
    stack.enter_context(patch('lokay.gh.check_comment'))
    stack.enter_context(patch('lokay.scope.code_scope_issue', return_value=None))
    merge = stack.enter_context(patch('lokay.merge.merge_sha'))
    prepare = stack.enter_context(patch('lokay.start._prepare', return_value={'result': 'fixture'}))
    # Distinct recorded probabilities prove the log does not repeat one answer.
    decisions = [dict(next='ok', uwagi=[], probabilities=[{'next': {'ok': .6 + n/100, 'issue': .4 - n/100}}])
                 for n in range(7)]
    decisions[0].update(next='issue', replan=green['replan'])
    decision = stack.enter_context(patch('lokay.check.decide_batches', side_effect=decisions))
    assert start._finish(picked, Path(tmp), 'lokay/1809', 'abc', []) == {'result': 'fixture'}
    assert decision.call_count == 7
    assert {call.args[0] for call in decision.call_args_list} == {p.stem.removeprefix('check_') for p in QUESTIONS.glob('check_*.json')}
    prepare.assert_called_once()
    merge.assert_not_called()
    saved = state.state_read(picked['repo'], picked['issue'])
    assert saved['node'] == 'plan' and 'wskaż konkret' in saved['plan_prompt']
    rounds = (state.run_dir(picked['repo'], picked['issue']) / 'rounds.md').read_text()
    entries = [line for line in rounds.splitlines() if 'Check lens ' in line and 'p=' in line][:7]
    assert len(entries) == len({line.split('p=', 1)[1] for line in entries}) == 7
    assert 'Check → Plan' in rounds

    stack.enter_context(patch('lokay.setup.prepare_dependencies'))
    stop_fix = stack.enter_context(patch('lokay.fix.fix_code', return_value={'result': 'failed'}))
    stack.enter_context(patch('lokay.gh.open_pr_for', return_value={'number': 1, 'headRefOid': 'abc'}))
    merge.return_value = {'result': 'merged', 'merge_sha': 'merged'}
    kinds = sorted(p.stem.removeprefix('check_') for p in QUESTIONS.glob('check_*.json'))
    for identical in (7, 4):
        state.state_update(picked['repo'], picked['issue'], node='check', verdict=None,
                           check_notes=[], fix_counts=[], fix_history=[], diff_fingerprint=None,
                           fix_fingerprint=None)
        decision.side_effect = [
            {'next': 'issue', 'uwagi': [{'plik': 'a.py', 'linia_od': 10, 'linia_do': 12,
              'zmiana': 'missing handling/validation' if n < identical else f'bug {n}',
              'pytanie': kind, 'p': .40 + n/100}], 'probabilities': []}
            for n, kind in enumerate(kinds)
        ]
        merge.reset_mock()
        stop_fix.reset_mock()
        with patch('sys.stderr') as stderr:
            outcome = start._finish(picked, Path(tmp), 'lokay/1809', 'abc', [])
        saved = state.state_read(picked['repo'], picked['issue'])
        if identical == 7:
            assert outcome['result'] == 'merged', outcome
            merge.assert_called_once()
            stop_fix.assert_not_called()
            assert saved['verdict']['uwagi'] == [] and len(saved['check_notes']) == 7
            assert stderr.write.called
            rounds = (state.run_dir(picked['repo'], picked['issue']) / 'rounds.md').read_text()
            assert 'Check degenerate answer: categories=' + ','.join(kinds) in rounds
            with patch('lokay.build.pr_body', return_value='base'), \
                 patch('lokay.start.open_pr_for', return_value={'number': 1}), \
                 patch('lokay.gh.pr_set_body', return_value={'result': 'updated'}) as update:
                refresh_body(picked['repo'], picked['issue'])
                body = update.call_args.args[2]
                assert '## Uwagi bez konkretu' in body
                assert all(kind in body for kind in kinds)
                assert 'a.py:10-12: missing handling/validation' in body
        else:
            assert outcome['result'] == 'failed'
            merge.assert_not_called()
            stop_fix.assert_called_once()
            assert len(saved['verdict']['uwagi']) == 7 and not saved['check_notes']
            assert not stderr.write.called
print('follow-up: relative threshold; issue without location → Plan; seven distinct lens logs; no merge OK')
PY
