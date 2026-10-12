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

def run(chosen, probability=.9, files=rows):
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
            answers[question['id']] = {'choice': choice, 'probabilities': probabilities, 'confidence': p}
        return answers
    result = decide_batches('correctness', files, {'sha': 'abc'}, decide)
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
low, _ = run('a.py:10-12', .84)
assert not low['uwagi'] and low['notes']
edge, _ = run('a.py:10-12', .85)
assert edge['uwagi']
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
