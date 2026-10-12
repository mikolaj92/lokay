#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import json
import os
import subprocess
import tempfile
from pathlib import Path

script = Path('scenarios/darkfactory-canary.sh').resolve()
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / 'bin').mkdir()
    fake = root / 'bin/gh'
    fake.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
p = Path(os.environ['FAKE_STORE'])
d = json.loads(p.read_text())
a = sys.argv[1:]
assert '--repo' in a and a[a.index('--repo')+1] == 'mikolaj92/lokay-sandbox', a
if a[:2] == ['issue', 'list']:
 print(json.dumps(d['issues']))
elif a[:2] == ['issue', 'create']:
 if d.get('fail'):
  sys.exit('creation failed')
 n = len(d['issues']) + 1
 d['issues'].append({'number': n, 'title': a[a.index('--title')+1]})
 p.write_text(json.dumps(d))
 print(f'https://github.com/mikolaj92/lokay-sandbox/issues/{n}')
elif a[:2] == ['pr', 'list']:
 print(json.dumps(d['prs']))
else:
 sys.exit(f'unexpected gh operation: {a}')
''')
    fake.chmod(0o755)
    store = root / 'external.json'
    store.write_text(json.dumps({'issues': [], 'prs': []}))
    env = {key: os.environ[key] for key in os.environ
           if key not in ('GH_TOKEN', 'GITHUB_TOKEN') and not key.startswith(('LOKAY', 'PI_'))}
    env.update(HOME=tmp, PATH=str(root/'bin')+os.pathsep+os.environ['PATH'],
               FAKE_STORE=str(store), LOKAY2_REPO='mikolaj92/lokay-sandbox')
    def tick(ok=True):
        result = subprocess.run(['bash', str(script)], env=env, capture_output=True, text=True)
        assert (result.returncode == 0) == ok, (result.stdout, result.stderr)
    tick()
    state_path = root / '.lokay/darkfactory-canary/state.json'
    state = json.loads(state_path.read_text())
    assert state['issues'] == [1, 2], state
    tick()
    assert len(json.loads(store.read_text())['issues']) == 2
    # A partial creation is recoverable without duplicating the first issue.
    state['issues'] = [1]
    state_path.write_text(json.dumps(state))
    tick()
    assert json.loads(state_path.read_text())['issues'] == [1, 2]
    assert len(json.loads(store.read_text())['issues']) == 2
    # No operations are allowed outside the sandbox.
    env['LOKAY2_REPO'] = 'example/other'
    before = store.read_bytes()
    tick(False)
    assert store.read_bytes() == before
    env['LOKAY2_REPO'] = 'mikolaj92/lokay-sandbox'
    runs = root / '.lokay/runs/mikolaj92__lokay-sandbox'
    data = json.loads(store.read_text())
    for n in (1, 2):
        run = runs / str(n)
        run.mkdir(parents=True)
        (run/'state.json').write_text(json.dumps({'result': 'merged', 'pr': 100+n, 'sha': f'sha{n}'}))
        (run/'rounds.md').write_text(f'Merge: sha=sha{n}\n')
        data['issues'][n-1]['state'] = 'CLOSED'
        data['prs'].append({'number': 100+n, 'url': f'https://github.com/mikolaj92/lokay-sandbox/pull/{100+n}',
                            'headRefName': f'lokay/{n}', 'mergedAt': f'2026-10-12T00:00:0{n+2}Z'})
        store.write_text(json.dumps(data))
        (root/'.lokay/heartbeat.json').write_text(json.dumps({'repo': 'mikolaj92/lokay-sandbox',
            'issue': n, 'result': 'merged', 'time': f'2026-10-12T00:00:0{n+2}Z'}))
        tick()
    state = json.loads(state_path.read_text())
    assert state['result'] == 'complete', state
    evidence = root / '.lokay/darkfactory-canary' / state['pair']
    assert len(json.loads((evidence/'proof.json').read_text())['prs']) == 2
    assert (evidence/'heartbeat-between.json').is_file()
    assert all((evidence/str(n)/'rounds.md').is_file() for n in (1,2))
    tick()
    assert len(json.loads(store.read_text())['issues']) == 2
    # Orphaned open issues must block a new pair, even with overdue state.
    state['created_at'] = 0
    state_path.write_text(json.dumps(state))
    data = json.loads(store.read_text())
    data['issues'][0]['state'] = 'OPEN'
    store.write_text(json.dumps(data))
    tick(False)
    assert len(json.loads(store.read_text())['issues']) == 2
    data['issues'][0]['state'] = 'CLOSED'
    store.write_text(json.dumps(data))
    tick()
    assert len(json.loads(store.read_text())['issues']) == 4
    state = json.loads(state_path.read_text())
    state['result'] = 'complete'
    state['created_at'] = 0
    state_path.write_text(json.dumps(state))
    data = json.loads(store.read_text())
    for row in data['issues']:
        row['state'] = 'CLOSED'
    data['fail'] = True
    store.write_text(json.dumps(data))
    tick(False)
    assert 'creation failed' in json.loads(state_path.read_text())['error']
service = Path('scripts/lokay-service.sh').read_text()
assert 'LOKAY_DARKFACTORY_CANARY' in service, 'caretaker has no opt-in canary hook'
assert service.index('bash "$ROOT/scenarios/darkfactory-canary.sh"') < service.index('"$ROOT/.venv/bin/lokay" start')
print('darkfactory canary: sandbox guard, pair recovery, evidence, recurrence, failure OK')
PY
