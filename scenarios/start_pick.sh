#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT
cat > "$root/gh" <<'EOF'
#!/bin/sh
printf '%s
' "$*" >> "$GH_LOG"
if [ "$1" = "auth" ]; then exit 0; fi
if [ "$1" = "issue" ]; then
  printf '%s
' '[{"number":2,"createdAt":"2026-10-09T01:00:00Z","title":"b"},{"number":3,"createdAt":"2026-10-08T01:00:00Z","title":"ePiC: skip"},{"number":1,"createdAt":"2026-10-09T01:00:00Z","title":"a"}]'
  exit 0
fi
if [ "$1" = "pr" ]; then
  case "$*" in
    *"--head lokay/1"*) printf '%s\n' '[]'; exit 0 ;;
  esac
  if [ "${OPEN_PR:-}" = "yes" ]; then
    if [ -n "${PR_ROWS:-}" ]; then
      printf '%s\n' "$PR_ROWS"
    else
      printf '%s\n' '[{"number":10,"headRefName":"lokay/2","headRefOid":"abc"}]'
    fi
    exit 0
  fi
  printf '%s
' '[]'
  exit 0
fi
exit 0
EOF
chmod +x "$root/gh"
cat > "$root/pi" <<'EOF'
#!/bin/sh
exit 0
EOF
chmod +x "$root/pi"
cat > "$root/repos.yaml" <<'EOF'
repos:
  - name: example/first
    clone_path: /unused
    test: ["python3", "verify.py"]
    merge: on
  - name: example/second
    clone_path: /unused
    test: ["python3", "verify.py"]
    merge: on
  - name: example/untested
    clone_path: /unused
    test: []
    merge: on
EOF
export LOKAY2_REPOS_FILE="$root/repos.yaml"
export GH_LOG="$root/calls"
export PATH="$root:$PATH"
export HOME="$root/home"
mkdir -p "$HOME"
: > "$GH_LOG"
uv run python - <<'PY'
import os
import json
from lokay import start
from lokay.start import pick
start.probes = lambda env=None: {"scenario": "ok"}
env = {
    "PATH": os.environ["PATH"],
    "HOME": os.environ["HOME"],
    "LOKAY2_GB10": "up",
    "LOKAY2_PROVIDER": "omniroute",
    "LOKAY2_MODEL": "m",
    "LOKAY2_DECISION_API": "tensorfold",
    "LOKAY2_DECISION_MODEL": "m",
    "LOKAY2_REPOS_FILE": os.environ["LOKAY2_REPOS_FILE"],
}
untested = pick({**env, "LOKAY2_REPO": "example/untested"})
assert untested["result"] == "picked" and untested["repo"] == "example/untested", untested
start.release(untested["held"])
got = pick(env)
assert got["issue"] == 1 and got["node"] == "plan" and got["repo"] == "example/first", got
assert pick({**env, "LOKAY2_REPO": "example/first"}) == {"result": "idle", "reason": "no_work"}
start.release(got["held"])
start.release(got["held"])
os.environ["OPEN_PR"] = "yes"
got = pick({**env, "LOKAY2_REPO": "example/second", "LOKAY2_ISSUE": "2"})
assert got["repo"] == "example/second" and got["issue"] == 2 and got["node"] == "check" and got["pr"] == 10, got
start.release(got["held"])
from lokay.state import state_update
import time
state_update('example/second', 2, retry_at=time.time() + 3600, failures=1, reason='fixture')
assert pick({**env, 'LOKAY2_REPO': 'example/second', 'LOKAY2_ISSUE': '2'}) == {
    'result': 'idle', 'reason': 'no_work'}
state_update('example/second', 2, node='plan', retry_at=0, failures=0, reason=None)
got = pick({**env, 'LOKAY2_REPO': 'example/second', 'LOKAY2_ISSUE': '2'})
assert got['node'] == 'plan' and got['pr'] == 10, got
start.release(got['held'])
assert pick({**env, "LOKAY2_ISSUE": "3"}) == {"result": "idle", "reason": "no_work"}
assert pick({**env, "LOKAY2_REPO": "example/missing"}) == {"result": "idle", "reason": "no_work"}
# Historical needs_help skip: only unskip may remove it.
start.skip_file().write_text(json.dumps({'example/second': {'2': 'needs_help: fix_code; pr=10 sha=abc', '99': 'keep'}}))
os.environ['PR_ROWS'] = '[{"number":10,"headRefName":"lokay/2","headRefOid":"abc"},{"number":11,"headRefName":"lokay/4","headRefOid":"def"}]'
got = pick({**env, 'LOKAY2_REPO': 'example/second'})
assert got['issue'] == 4 and got['pr'] == 11, got
start.release(got['held'])
os.environ['PR_ROWS'] = '[{"number":10,"headRefName":"lokay/2","headRefOid":"abc"}]'
got = pick({**env, 'LOKAY2_REPO': 'example/second'})
assert got['issue'] == 1 and got['node'] == 'plan', got
start.release(got['held'])
from lokay.cli import main as cli_main
state_update('example/second', 2, retry_at=time.time() + 3600)
assert cli_main(['unskip', 'example/second', '2']) == 0
assert start.load_skips('example/second') == {99}
from lokay.state import state_read
assert state_read('example/second', 2)['retry_at'] == 0
assert cli_main(['unskip', 'example/second', '2']) == 0
assert start.load_skips('example/second') == {99}
got = pick({**env, 'LOKAY2_REPO': 'example/second', 'LOKAY2_ISSUE': '2'})
assert got['issue'] == 2 and got['pr'] == 10, got
start.release(got['held'])
start.skip_file().unlink()
assert cli_main(['unskip', 'example/second', '2']) == 0
assert not start.skip_file().exists()
assert "--label" not in open(os.environ["GH_LOG"]).read()
# Exceptions before selection release exactly once, not in except and finally.
from unittest.mock import patch
os.environ.pop('OPEN_PR', None)
with patch('lokay.start.open_issues', side_effect=RuntimeError('lookup failed')), \
     patch('lokay.start.release', wraps=start.release) as released:
    try:
        pick({**env, 'LOKAY2_REPO': 'example/first'})
    except RuntimeError as exc:
        assert str(exc) == 'lookup failed'
    else:
        raise AssertionError('missing lookup failure')
    released.assert_called_once()
print("pick: oldest, tie-break, Epic, overrides, open PR, exception release OK")
PY
rm -rf "$root"
