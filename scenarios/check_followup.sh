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
assert noted['notes'] == [{'pytanie': 'correctness', 'note': 'issue without concrete finding after follow-up'}]
green = aggregate('abc', {'sha': 'abc', 'result': 'green'}, [noted])
assert green['result'] == 'merge' and green['notes'] == noted['notes']
red = aggregate('abc', {'sha': 'abc', 'result': 'red', 'failed': [{'warstwa': 'CI'}]}, [noted])
assert red['result'] == 'fix' and red['uwagi'] == [{'warstwa': 'CI'}]
from unittest.mock import patch
from lokay.check import FOLLOWUP_THRESHOLD, THRESHOLD
assert FOLLOWUP_THRESHOLD == .5 and THRESHOLD == .85
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
    run('none', kind='correctness alignment architecture security production scope tests')
    assert log.call_count == 7
    for call, kind in zip(log.call_args_list, 'correctness alignment architecture security production scope tests'.split()):
        assert f'Check follow-up {kind}:' in call.args[2]
for distribution in (
    {'a.py:10-12': .49, 'b.py:1-2': .31, 'none': .2},
    {'a.py:10-12': .5, 'b.py:1-2': .24, 'none': .26},
):
    low, _ = run('a.py:10-12', files=files, distribution=distribution)
    assert not low['uwagi'] and low['notes']
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
assert len(noted['notes']) == 1
from pathlib import Path
from unittest.mock import patch
from lokay.gh import check_comment
from lokay import start
with patch('lokay.gh._gh', return_value=(0, 'url', '')) as gh:
    check_comment('example/repo', 1, 1, green, {'result': 'green'})
    body = gh.call_args.args[0][-1]
    assert '## Uwagi bez konkretu' in body and 'correctness' in body
with patch('lokay.start.load_repos', return_value=[{'name': 'example/repo', 'clone_path': '/tmp/clone'}]), \
     patch('lokay.start.open_pr_for', return_value={'number': 1}), \
     patch('lokay.start.state_read', return_value={'verdict': green}), \
     patch('lokay.build.pr_body', return_value='base'), \
     patch('lokay.gh.pr_set_body', return_value={'result': 'updated'}) as update:
    start.refresh_body('example/repo', 1)
    assert '## Uwagi bez konkretu' in update.call_args.args[2]
    assert 'correctness' in update.call_args.args[2]

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
print('follow-up: concrete → fix; none → note → merge; red CI → fix; threshold, batches, PR notes, empty Fix recovery OK')
PY
