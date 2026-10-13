#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
tmp=$(mktemp -d)
cat > "$tmp/gh" <<'EOF'
#!/bin/sh
printf '%s
' "$*" >> "$GH_LOG"
if [ "$1" = "pr" ] && [ "$2" = "merge" ]; then
  echo "$*" | grep -q -- "--match-head-commit $SHA" || exit 1
  exit 0
fi
exit 0
EOF
chmod +x "$tmp/gh"
export PATH="$tmp:$PATH"
export GH_LOG="$tmp/log"
export SHA=abc123
export HOME="$tmp/home"
mkdir -p "$HOME"
: > "$GH_LOG"
uv run python - <<'PY'
import os
from pathlib import Path
from lokay.merge import merge_sha
from lokay.lock import acquire, release
from lokay import state
from unittest.mock import patch
import subprocess
import io
import logging

home_repo = "mikolaj92/lokay-sandbox"
held = acquire("mikolaj92", home_repo)
got = merge_sha(home_repo, 3, os.environ["SHA"], {"result": "merge", "sha": os.environ["SHA"]}, None, held, "mikolaj92", 3, {"plan_rounds": 1, "check_rounds": 1})
assert got["result"] == "merged", got
log = Path(os.environ["GH_LOG"]).read_text()
assert "--match-head-commit" in log and os.environ["SHA"] in log
moved = merge_sha(home_repo, 3, "other", {"result": "merge", "sha": os.environ["SHA"]}, None, None, "mikolaj92", 3, {})
assert moved["result"] == "sha_moved"
assert acquire('mikolaj92', home_repo)['result'] == 'busy', 'merge must not release the run lock'
release(held)
again = acquire("mikolaj92", home_repo)
assert again["result"] == "held"
release(again)

# A real clone owns the worktree; its parent is not a Git repository.
root = Path(os.environ['HOME']).parent
origin = root / 'origin.git'
clone = root / 'main'
wt = root / 'main-wt-1783'
def git(*args):
    return subprocess.check_output(['git', *map(str, args)], text=True, stderr=subprocess.STDOUT)
git('init', '--bare', '-b', 'main', origin)
git('clone', origin, clone)
git('-C', clone, 'config', 'user.name', 'mikolaj92')
git('-C', clone, 'config', 'user.email', 'fixture@example.invalid')
(clone / 'code.py').write_text('pass\n')
git('-C', clone, 'add', '.')
git('-C', clone, 'commit', '-m', 'fixture')
git('-C', clone, 'worktree', 'add', '-b', 'fixture', wt)
held = acquire('mikolaj92', home_repo)
with patch('lokay.merge.gh_merge', return_value={'result': 'merged'}):
    assert merge_sha(home_repo, 3, 'abc', {'result': 'merge', 'sha': 'abc'}, wt, held,
                     'mikolaj92', 1783, {}, clone_path=clone)['result'] == 'merged'
assert not wt.exists()
assert str(wt) not in git('-C', clone, 'worktree', 'list', '--porcelain')
assert acquire('mikolaj92', home_repo)['result'] == 'busy'
release(held)

# A locked worktree blocks real git cleanup even with --force.
git('-C', clone, 'worktree', 'add', wt, 'fixture')
git('-C', clone, 'worktree', 'lock', '--reason', 'scenario cleanup blocked', wt)
held = acquire('mikolaj92', home_repo)
warning = io.StringIO()
handler = logging.StreamHandler(warning)
logger = logging.getLogger('lokay.merge')
logger.addHandler(handler)
state.state_update(home_repo, 1783, failures=2, reason='old error', last_error='old error')
with patch('lokay.merge.gh_merge', return_value={'result': 'merged'}):
    got = merge_sha(home_repo, 3, 'abc', {'result': 'merge', 'sha': 'abc'}, wt, held,
                    'mikolaj92', 1783, {}, clone_path=clone)
assert got['result'] == 'merged' and wt.exists()
assert state.state_read(home_repo, 1783)['result'] == 'merged'
assert state.state_read(home_repo, 1783)['failures'] == 0
assert 'worktree cleanup failed' in warning.getvalue() and str(wt) in warning.getvalue()
assert 'locked' in warning.getvalue()
# An exception from cleanup is also only a warning.
with patch('lokay.merge.gh_merge', return_value={'result': 'merged'}), \
     patch('lokay.merge.worktree_remove', side_effect=OSError('cannot remove')):
    assert merge_sha(home_repo, 3, 'abc', {'result': 'merge', 'sha': 'abc'}, wt, held,
                     'mikolaj92', 1783, {}, clone_path=clone)['result'] == 'merged'
assert 'cannot remove' in warning.getvalue()
logger.removeHandler(handler)
git('-C', clone, 'worktree', 'unlock', wt)
assert acquire('mikolaj92', home_repo)['result'] == 'busy'
release(held)
with patch('lokay.merge.gh_merge') as merge:
    merge_sha(home_repo, 3, 'abc', {'result': 'fix', 'sha': 'abc'}, None, None,
              'mikolaj92', 1783, {})
    merge.assert_not_called()

expected = state.RUNS / 'mikolaj92__lokay' / '1783' / 'state.json'
for repo in ('lokay', 'mikolaj92/lokay'):
    assert state.run_path('mikolaj92', repo, 1783) == expected
    assert state.write_run('mikolaj92', repo, 1783, {'sha': 'real'}) == expected
    assert state.read_run('mikolaj92', repo, 1783)['sha'] == 'real'
assert expected.parent == state.run_dir('mikolaj92/lokay', 1783)
(expected.parent / 'plan.md').write_text('plan')
assert not (state.RUNS / 'mikolaj92__mikolaj92__lokay').exists()
print("merged")
print("sha_moved")
PY
rm -rf "$tmp"
