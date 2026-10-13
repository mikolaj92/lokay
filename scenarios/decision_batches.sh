#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
uv run --offline python - <<'PY'
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from lokay.check import hunks, check_state, decide_batches, local_ci
from lokay.decide import to_wire
from subprocess import CompletedProcess

parts = []
for file in range(60):
    parts.append(f'diff --git a/f{file}.py b/f{file}.py\n--- a/f{file}.py\n+++ b/f{file}.py\n')
    for h in range(4 if file < 20 else 3):
        parts.append(f'@@ -{10*h+1},1 +{10*h+1},1 @@\n-old\n+new\n')
diff = ''.join(parts)
assert diff.count('@@ -') == 200
rows = hunks(diff)
assert len(rows) == 60 and rows[0]['linia_od'] == 1 and rows[0]['linia_do'] == 31
assert rows[0]['added'] == rows[0]['deleted'] == 4
assert '@@ -1,1 +1,1 @@\n-old\n+new' in rows[0]['body']
assert len(hunks(diff.replace('+new', '+' + 'x' * 10000))[0]['body']) == 1500
assert hunks('diff --git a/gone b/gone\n--- a/gone\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-a\n-b\n')[0]['deleted'] == 2
with tempfile.TemporaryDirectory() as tmp:
    full_log = 'failure\n' * 2000
    with patch('lokay.run.run_process', return_value=CompletedProcess([], 1, full_log, '')):
        ci = local_ci('sha', [['false']], tmp)
    assert ci['log'] == full_log + '\nRetry:\n' + full_log
    state = check_state(Path(tmp), 3, diff, 'stat\n' * 500, ci, sha='sha')
    assert Path(state['diff_path']).read_text() == diff
    assert Path(state['test_log_path']).read_text() == ci['log']
    assert len(state['diff_stat']) == 1500 and len(state['failures'][0]['log']) == 800
    for api in ('mini', 'systemone', 'tensorfold', 'openai-decisions'):
        calls = []
        def decide(request):
            wire = to_wire(api, 'm', request)
            assert len(json.dumps(wire)) < 5500, len(json.dumps(wire))
            calls.append(request)
            assert request['state']['hunks']
            assert all('+new' in body and '-old' in body for body in request['state']['hunks'].values())
            issue = len(calls) == 2
            return {q['id']: {'choice': ('issue' if issue else 'ok') if q['id'] == 'next' else ('true' if issue else 'false'),
                'probabilities': ({'issue': .9, 'ok': .1} if issue else {'ok': .9, 'issue': .1}) if q['id'] == 'next' else ({'true': .9, 'false': .1} if issue else {'false': .9, 'true': .1}),
                'confidence': .9} for q in request['questions']}
        with patch.dict(os.environ, LOKAY2_DECISION_API=api, LOKAY2_DECISION_MODEL='m'):
            result = decide_batches('correctness', rows, state, decide)
        assert len(calls) > 1 and result['next'] == 'issue' and result['uwagi']
        assert sum(len(call['questions']) - 1 for call in calls) == 60
        assert len({q['instructions'].split()[-1] for call in calls for q in call['questions'][1:]}) == 60
        assert len(result['uwagi']) == len(calls[1]['questions']) - 1
    for api in ('mini', 'systemone', 'tensorfold', 'openai-decisions'):
        internal = {'state': {'numbers': list(range(10000))}, 'questions': [{'id': 'q', 'type': 'bool', 'instructions': 'x' * 20000, 'options': {'true': 'yes', 'false': 'no'}}]}
        assert len(json.dumps(to_wire(api, 'm', internal))) < 6000
print('decision batches: 200 hunks / 60 files, four APIs, merged results, full artifacts OK')
PY
