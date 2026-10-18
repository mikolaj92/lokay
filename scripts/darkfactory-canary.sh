#!/usr/bin/env bash
set -euo pipefail
uv run --project "$(dirname "$0")/.." python - <<'PY'
import fcntl
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

from lokay.effects.gh import _gh

REPO = 'mikolaj92/lokay-sandbox'
if os.environ.get('LOKAY2_REPO') != REPO:
    raise SystemExit('canary requires LOKAY2_REPO=mikolaj92/lokay-sandbox')
root = Path.home() / '.lokay/darkfactory-canary'
root.mkdir(parents=True, exist_ok=True)
lock = (root / 'lock').open('a')
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    raise SystemExit('canary already running')
path = root / 'state.json'
state = json.loads(path.read_text()) if path.exists() else {}

def save():
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2) + '\n')
    temporary.replace(path)

def gh(*args):
    code, out, err = _gh([*args, '--repo', REPO])
    if code:
        raise RuntimeError(err.strip() or 'gh failed')
    return out.strip()

def stamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()

try:
    issues = json.loads(gh('issue', 'list', '--state', 'all', '--limit', '1000000', '--json', 'number,title,state'))
    if not state or (state.get('result') == 'complete' and time.time() - state['created_at'] >= 86400):
        active = [row for row in issues if row['title'].startswith('[darkfactory ') and row.get('state', 'OPEN') == 'OPEN']
        if active:
            raise RuntimeError('active canary issues exist; retain/recover local state before creating another pair')
        state = {'pair': uuid.uuid4().hex, 'created_at': time.time(), 'issues': [], 'result': 'creating'}
        save()
    if state.get('result') != 'complete':
        tasks = [
            ('slugify', 'Implement slugify(text) in darkfactory_slugify.py using the standard library. '
             'Lowercase ASCII words and join them with hyphens. Add a runnable unittest script '
             'test_darkfactory_slugify.py covering empty input, whitespace and punctuation. '
             'If already implemented, add a missing edge case and its regression test.'),
            ('version', 'Implement darkfactory_cli.py with --version printing 1.0.0 and exit code 0. '
             'Add test_darkfactory_cli.py using unittest and subprocess to verify stdout and exit code. '
             'If already implemented, add a regression test for invalid arguments and fix any failure.'),
        ]
        for index, (name, body) in enumerate(tasks):
            if len(state['issues']) > index:
                continue
            title = f"[darkfactory {state['pair']}] {name}"
            existing = [row for row in issues if row['title'] == title]
            if len(existing) > 1:
                raise RuntimeError('duplicate canary title: ' + title)
            if existing:
                number = existing[0]['number']
            else:
                url = gh('issue', 'create', '--title', title, '--body', body)
                number = int(url.rstrip('/').rsplit('/', 1)[1])
            state['issues'].append(number)
            save()
        state['result'] = 'active'
        evidence = root / state['pair']
        evidence.mkdir(exist_ok=True)
        runs = Path.home() / '.lokay/runs/mikolaj92__lokay-sandbox'
        prs = json.loads(gh('pr', 'list', '--state', 'merged', '--limit', '1000000',
                           '--json', 'number,url,headRefName,mergedAt'))
        proof = []
        for number in state['issues']:
            run = runs / str(number)
            if not (run / 'state.json').exists():
                continue
            saved = json.loads((run / 'state.json').read_text())
            matches = [pr for pr in prs if pr['number'] == saved.get('pr')
                       and pr['headRefName'] == f'lokay/{number}' and pr['mergedAt']]
            if saved.get('result') != 'merged' or len(matches) != 1:
                continue
            target = evidence / str(number)
            target.mkdir(exist_ok=True)
            for name in ('state.json', 'rounds.md'):
                (target / name).write_bytes((run / name).read_bytes())
            proof.append({**matches[0], 'issue': number, 'run': str(run), 'sha': saved['sha']})
        between = evidence / 'heartbeat-between.json'
        if len(proof) == 1 and proof[0]['issue'] == state['issues'][0] and not between.exists():
            beat = Path.home() / '.lokay/heartbeat.json'
            if beat.exists():
                data = json.loads(beat.read_text())
                if data.get('repo') == REPO and stamp(data['time']) >= stamp(proof[0]['mergedAt']):
                    between.write_bytes(beat.read_bytes())
        if len(proof) == 2:
            if not between.exists():
                raise RuntimeError('two merges found but heartbeat between runs was not observed')
            beat_time = stamp(json.loads(between.read_text())['time'])
            if not stamp(proof[0]['mergedAt']) <= beat_time < stamp(proof[1]['mergedAt']):
                raise RuntimeError('heartbeat is not between the two merges')
            (evidence / 'proof.json').write_text(json.dumps({'repo': REPO, 'pair': state['pair'], 'prs': proof}, indent=2) + '\n')
            state['result'] = 'complete'
    state.pop('error', None)
    save()
    print(json.dumps(state))
except Exception as exc:
    state['error'] = str(exc)
    save()
    raise SystemExit(str(exc))
PY
