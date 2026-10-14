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
if [ "$1" = "pr" ] && [ "$2" = "view" ]; then
  printf '{"mergeCommit":{"oid":"%s"}}\n' "$SHA"
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
with patch('lokay.merge.check_main', return_value={'status': 'green'}):
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
with patch('lokay.merge.check_main', return_value={'status': 'green'}), \
     patch('lokay.merge.gh_merge', return_value={'result': 'merged', 'merge_sha': 'abc'}):
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
with patch('lokay.merge.check_main', return_value={'status': 'green'}), \
     patch('lokay.merge.gh_merge', return_value={'result': 'merged', 'merge_sha': 'abc'}):
    got = merge_sha(home_repo, 3, 'abc', {'result': 'merge', 'sha': 'abc'}, wt, held,
                    'mikolaj92', 1783, {}, clone_path=clone)
assert got['result'] == 'merged' and wt.exists()
assert state.state_read(home_repo, 1783)['result'] == 'merged'
assert state.state_read(home_repo, 1783)['failures'] == 0
assert 'worktree cleanup failed' in warning.getvalue() and str(wt) in warning.getvalue()
assert 'locked' in warning.getvalue()
# An exception from cleanup is also only a warning.
with patch('lokay.merge.check_main', return_value={'status': 'green'}), \
     patch('lokay.merge.gh_merge', return_value={'result': 'merged', 'merge_sha': 'abc'}), \
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
import json
import sys
from collections import Counter
from lokay import main_guard, start
from lokay.observe import heartbeat

config = {'name': home_repo, 'clone_path': str(clone), 'setup': [],
          'test': [sys.executable, '-c',
                   "from pathlib import Path; import sys; red = Path('main-red').read_text().strip() == 'red'; print('1 failed' if red else '1 passed'); sys.exit(int(red))"]}
(clone / 'main-red').write_text('red\n')
git('-C', clone, 'add', 'main-red')
git('-C', clone, 'commit', '-m', 'break main')
culprit = git('-C', clone, 'rev-parse', 'HEAD').strip()
git('-C', clone, 'push', 'origin', 'main')
rows = []
calls = Counter()
def issue_gh(args):
    assert args[0] == 'issue' and args[1] in ('list', 'create', 'edit', 'reopen'), args
    action = args[1]
    calls[action] += 1
    assert args[args.index('--repo') + 1] == home_repo
    if action == 'list':
        return 0, json.dumps(rows), ''
    if action == 'create':
        assert not rows
        rows.append({'number': 81, 'title': args[args.index('--title') + 1],
                     'body': args[args.index('--body') + 1], 'state': 'OPEN'})
        return 0, f'https://github.com/{home_repo}/issues/81', ''
    assert int(args[2]) == rows[0]['number']
    if action == 'edit':
        rows[0].update(title=args[args.index('--title') + 1], body=args[args.index('--body') + 1])
    else:
        rows[0]['state'] = 'OPEN'
    return 0, '', ''

with patch('lokay.main_guard.load_repos', return_value=[config]), \
     patch('lokay.main_guard._gh', side_effect=issue_gh):
    red = main_guard.check_main(home_repo, clone, culprit, 73)
    assert red['status'] == 'red' and red['issue'] == 81
    assert red['culprit'] == {'sha': culprit, 'pr': 73}
    first_body = rows[0]['body']
    rows[0]['state'] = 'CLOSED'
    again = main_guard.check_main(home_repo, clone, culprit, 73)
    assert again == red
    assert len(rows) == 1 and calls == Counter(list=2, create=1, edit=1, reopen=1), calls
    assert rows[0]['state'] == 'OPEN' and rows[0]['body'] == first_body
    assert f'Merge SHA: `{culprit}` · PR: #73 · tested SHA: `{culprit}`' in first_body
    assert 'diff --git a/main-red b/main-red' in first_body and '+red' in first_body
    assert 'break main' in first_body and '1 failed' in first_body and 'Retry:' in first_body
    assert state.main_status()[home_repo] == red
    assert heartbeat()['main_status'][home_repo] == red
    assert json.loads((Path.home() / '.lokay/heartbeat.json').read_text())['main_status'][home_repo] == red
    other = {'name': 'mikolaj92/other', 'clone_path': str(clone)}
    normal_pr = {'number': 99, 'headRefName': 'lokay/9', 'headRefOid': culprit}
    def competing_prs(args):
        assert args[:2] == ['pr', 'list']
        return 0, json.dumps([normal_pr] if args[args.index('--repo') + 1] == other['name'] else []), ''
    with patch('lokay.start.probes', return_value={'git': 'ok', 'gh': 'ok', 'pi': 'ok'}), \
         patch('lokay.start.load_repos', return_value=[other, config]), \
         patch('lokay.start.open_pr_for', return_value=None) as open_pr, \
         patch('lokay.start._gh', side_effect=competing_prs) as pr_list:
        chosen = start.pick({})
        assert chosen['result'] == 'picked' and chosen['repo'] == home_repo, chosen
        assert chosen['issue'] == 81 and chosen['node'] == 'plan' and chosen['pr'] is None
        open_pr.assert_called_once_with(home_repo, 'lokay/81')
        pr_list.assert_not_called()
        release(chosen['held'])
    (clone / 'main-red').write_text('green\n')
    git('-C', clone, 'add', 'main-red')
    git('-C', clone, 'commit', '-m', 'repair main')
    repaired = git('-C', clone, 'rev-parse', 'HEAD').strip()
    git('-C', clone, 'push', 'origin', 'main')
    green = main_guard.check_main(home_repo, clone, repaired, 74)
    assert green['status'] == 'green' and green['issue'] == 81
    assert green['culprit'] == {'sha': repaired, 'pr': 74}
    assert state.main_status()[home_repo] == green
    assert heartbeat()['main_status'][home_repo] == green
    assert calls == Counter(list=2, create=1, edit=1, reopen=1) and rows[0]['state'] == 'OPEN'
    with patch('lokay.start.probes', return_value={'git': 'ok', 'gh': 'ok', 'pi': 'ok'}), \
         patch('lokay.start.load_repos', return_value=[other, config]), \
         patch('lokay.start.open_pr_for', return_value=None), \
         patch('lokay.start._gh', side_effect=competing_prs):
        chosen = start.pick({})
        assert chosen['result'] == 'picked' and chosen['repo'] == other['name'], chosen
        assert chosen['issue'] == 9 and chosen['pr'] == 99 and chosen['node'] == 'check'
        release(chosen['held'])
    assert 'lokay-main-' not in git('-C', clone, 'worktree', 'list', '--porcelain')

order = []
def checked(*args):
    order.append('check_main')
    assert args == (home_repo, clone, repaired, 74)
    return green

def deployed(*args):
    assert order == ['check_main'] and args == (home_repo, repaired)
    order.append('pre_deploy')
    return {'pass': True}

with patch('lokay.merge.gh_merge', return_value={'result': 'merged', 'merge_sha': repaired}), \
     patch('lokay.merge.check_main', side_effect=checked), \
     patch('lokay.merge.pre_deploy', side_effect=deployed):
    assert merge_sha(home_repo, 74, repaired, {'result': 'merge', 'sha': repaired}, None,
                     None, 'mikolaj92', 81, {}, clone_path=clone)['result'] == 'merged'
assert order == ['check_main', 'pre_deploy']
print("merged")
print("sha_moved")
print(f"main_guard: red=2 green=1 issues={len(rows)} create={calls['create']} edit={calls['edit']} reopen={calls['reopen']} close={calls['close']} priority=guard deploy=after_check")
PY
rm -rf "$tmp"
