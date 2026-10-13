#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
uv run --offline python - <<'PY'
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from lokay import start, state

repos = [{'name': 'example/first'}, {'name': 'example/second'}]
rows = {'example/first': [{'number': 1, 'headRefName': 'lokay/11'}],
        'example/second': [{'number': 20, 'headRefName': 'lokay/22'},
                           {'number': 30, 'headRefName': 'lokay/33'}]}
def gh(args):
    return 0, json.dumps(rows[args[args.index('--repo') + 1]]), ''
with tempfile.TemporaryDirectory() as tmp, \
     patch.object(state, 'RUNS', Path(tmp)), \
     patch('lokay.start.probes', return_value={'fixture': 'ok'}), \
     patch('lokay.start.load_repos', return_value=repos), \
     patch('lokay.start.load_skips', return_value=set()), \
     patch('lokay.start._gh', side_effect=gh), \
     patch('lokay.start.acquire', return_value={'result': 'held'}), \
     patch('lokay.start.release'):
    state.state_update('example/first', 11, last_attempt=200)
    state.state_update('example/second', 22, last_attempt=100)
    state.state_update('example/second', 33, last_attempt=150)
    before = time.time()
    got = start.pick({})
    assert (got['repo'], got['pr']) == ('example/second', 20), got
    assert state.state_read('example/second', 22)['last_attempt'] >= before
    got = start.pick({})
    assert got['pr'] == 1, got  # A busy repo cannot take consecutive ticks.
    state.state_update('example/second', 22, last_attempt=0)
    state.state_update('example/first', 11, last_attempt=0)
    state.state_update('example/second', 33, last_attempt=0)
    for repo in repos:
        state.repo_attempt(repo['name'], 0)
    got = start.pick({})
    assert got['pr'] == 1, got  # Repo ties use name; PR ties use number.
    with patch('lokay.start.acquire', side_effect=lambda owner, repo:
               {'result': 'busy' if repo == 'example/second' else 'held'}):
        got = start.pick({})
        assert got['repo'] == 'example/first', got
    rows = {repo['name']: [] for repo in repos}
    with patch('lokay.start.open_issues', return_value=[{'number': 44, 'title': 'fix'}]), \
         patch('lokay.start.open_pr_for', return_value=None):
        got = start.pick({})
        assert state.state_read(got['repo'], 44)['last_attempt'] >= before
print('fair_pick: global order, repo order, ties, busy locks, timestamps OK')
PY
