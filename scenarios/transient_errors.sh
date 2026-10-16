set -eu
cd "$(dirname "$0")/.."
mkdir -p .local
TRANSIENT_ROOT=$(mktemp -d "$PWD/.local/transient.XXXXXX")
export TRANSIENT_ROOT
trap 'rm -rf "$TRANSIENT_ROOT"' EXIT HUP INT TERM
export HOME="$TRANSIENT_ROOT/home" TMPDIR="$TRANSIENT_ROOT/tmp"
mkdir -p "$HOME" "$TMPDIR"
.venv/bin/python - <<'PY'
import json
import os
import sys
from pathlib import Path

from contextlib import nullcontext

from lokay import store
from lokay.effects import decide, gh, pi

root = Path(os.environ['TRANSIENT_ROOT'])
store.RUNS = root / 'runs'
stub = root / 'provider.py'
stub.write_text('''import json
import os
import sys
from pathlib import Path
root = Path(os.environ['TRANSIENT_ROOT'])
args = sys.argv[1:]
count = root / 'count'
n = int(count.read_text()) + 1 if count.exists() else 1
count.write_text(str(n))
mode = os.environ['TRANSIENT_MODE']
if mode == 'curl':
    print('{}')
    sys.stdout.write(os.environ['TRANSIENT_STATUS'] if n <= int(os.environ['TRANSIENT_FAILURES']) else '200')
    sys.exit(0)
if mode == 'comment':
    if args[0] == 'api':
        print(json.dumps([[{'body': (root / 'body').read_text(), 'html_url': 'https://example/comment'}]]))
        sys.exit(0)
    (root / 'body').write_text(args[args.index('--body') + 1])
    print('GraphQL: Something went wrong while executing your query', file=sys.stderr)
    sys.exit(1)
if n <= int(os.environ['TRANSIENT_FAILURES']):
    print(os.environ['TRANSIENT_ERROR'], file=sys.stderr)
    sys.exit(int(os.environ.get('TRANSIENT_EXIT', '1')))
print('ok')
''')
os.environ['TRANSIENT_ROOT'] = str(root)
os.environ['TRANSIENT_MODE'] = 'error'
count = root / 'count'
original_sleep = pi.retry_sleep
delays = []
pi.retry_sleep = delays.append
for transport, error, failures, attempts, pauses in (
    ('pi', 'Error: 503 service unavailable', 1, 2, [1]),
    ('pi', 'HTTP 429', 8, 4, [1, 2, 4]),
    ('pi', 'HTTP 401', 8, 1, []),
    ('pi', 'HTTP 403', 8, 1, []),
    ('pi', 'semantic failure at line 503', 8, 1, []),
    ('pi', 'missing artifact', 8, 1, []),
    ('gh', 'GraphQL: Something went wrong while executing your query', 1, 2, [1]),
    ('gh', 'HTTP 502', 8, 4, [1, 2, 4]),
    ('gh', 'HTTP 403', 8, 1, []),
    ('curl', 'curl: (52) Empty reply from server', 1, 2, [1]),
):
    count.unlink(missing_ok=True)
    delays.clear()
    os.environ.update(TRANSIENT_ERROR=error, TRANSIENT_FAILURES=str(failures),
                      TRANSIENT_EXIT='52' if transport == 'curl' else '1')
    proc = pi.run_process([sys.executable, str(stub)], retry=transport)
    assert int(count.read_text()) == attempts, (transport, error, count.read_text())
    assert delays == pauses, (error, delays)
    assert proc.returncode == (0 if failures < attempts else int(os.environ['TRANSIENT_EXIT']))
count.unlink()
delays.clear()
os.environ.update(TRANSIENT_ERROR='HTTP 503', TRANSIENT_FAILURES='8')
pi.run_process([sys.executable, str(stub)])
assert count.read_text() == '1' and not delays
curl = root / 'curl'
curl.write_text('#!' + sys.executable + '\n' + stub.read_text())
curl.chmod(0o755)
os.environ.update(PATH=str(root) + os.pathsep + os.environ['PATH'],
                  LOKAY2_DECISION_API='mini', LOKAY2_DECISION_BASE_URL='http://local',
                  TRANSIENT_MODE='curl', TRANSIENT_FAILURES='1')
for status in ('408', '429', '500', '502', '503', '599', '401', '403', '200'):
    count.unlink(missing_ok=True)
    delays.clear()
    os.environ['TRANSIENT_STATUS'] = status
    try:
        decide._decide({'state': {}, 'questions': []})
    except (decide.DecisionError, KeyError, TypeError):
        pass
    expected = 2 if status in ('408', '429', '500', '502', '503', '599') else 1
    assert int(count.read_text()) == expected, (status, count.read_text(), delays)
    assert delays == ([1] if expected == 2 else [])
executable = root / 'pi'
executable.write_text('#!' + sys.executable + '\n' + stub.read_text())
executable.chmod(0o755)
count.unlink()
delays.clear()
os.environ.update(TRANSIENT_MODE='error', TRANSIENT_ERROR='HTTP 503', TRANSIENT_FAILURES='1', TRANSIENT_EXIT='1')
pi._pi_admission = lambda *args: nullcontext()
proc = pi.run_process([str(executable), '-p', 'local scenario'], cwd=Path.cwd(), retry='pi')
assert proc.returncode == 0 and count.read_text() == '2' and delays == [1]
for path in ('src/lokay/build.py', 'src/lokay/fix.py', 'src/lokay/effects/pi.py'):
    assert 'retry="pi"' in Path(path).read_text()
wire = decide._trim_wire({'state': {'log': '\"\\😀' * 10000}, 'questions': []})
assert len(json.dumps(wire)) < 6000
count.unlink()
delays.clear()
os.environ['TRANSIENT_MODE'] = 'comment'
executable = root / 'gh'
executable.write_text('#!' + sys.executable + '\n' + stub.read_text())
executable.chmod(0o755)
verdict = {'sha': 'abc', 'result': 'pass', 'uwagi': ['😀\\\"' * 30000]}
result = gh.check_comment('owner/repo', 1, 2, verdict, {'result': 'pass'})
assert result['url'] == 'https://example/comment'
assert count.read_text() == '2' and not delays
body = (root / 'body').read_text()
assert len(body) <= 60000 and body.endswith(' -->') and '<!-- lokay-check:1:2:' in body
suffix = '\n\nCloses #1924\n\nOpened by lokay.\n'
text = gh.fit_body('😀\\\"' * 30000, 60000 - len(suffix)) + suffix
assert len(text) <= 60000 and text.endswith(suffix)
assert json.loads(json.dumps(text)) == text
pi.retry_sleep = original_sleep
print('transient_errors: transport retries, exhaustion, backoff, permanent errors, Decision, comment reconciliation and Unicode OK')
PY
