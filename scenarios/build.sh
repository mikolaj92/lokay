#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
tmp=$(mktemp -d)
bare="$tmp/bare.git"
src="$tmp/src"
git init --bare -b main "$bare" >/dev/null
git clone "$bare" "$src" >/dev/null 2>&1
git -C "$src" config user.email a@b.c
git -C "$src" config user.name t
echo base > "$src/f"
git -C "$src" add f && git -C "$src" commit -m base >/dev/null
git -C "$src" push -u origin main >/dev/null 2>&1
cat > "$tmp/pi" <<'EOF'
#!/bin/sh
env | sort > "$PI_ENV"
echo code > a.py
git add a.py
git commit -m 'pi commit' >/dev/null
printf '%1600s' '' | tr ' ' x
printf '\nDodano a.py z implementacją.\n'
exit 0
EOF
chmod +x "$tmp/pi"
cat > "$tmp/gh" <<'EOF'
#!/bin/sh
printf '%s
' "$*" >> "$GH_LOG"
echo "https://example.test/pull/1"
exit 0
EOF
chmod +x "$tmp/gh"
export PATH="$tmp:$PATH"
export PI_ENV="$tmp/env"
export GH_LOG="$tmp/gh.log"
export HOME="$tmp/home"
mkdir -p "$HOME"
: > "$GH_LOG"
uv run python - "$src" <<'PY'
import os, sys
from pathlib import Path
from lokay.build import build_code, build_publish, child_env, tidy_and_commit, _git
from lokay.state import state_update, state_read, run_dir
from lokay.start import refresh_body
from unittest.mock import patch

repo = Path(sys.argv[1])
wt = repo.parent / "wt"
from lokay.git import worktree_add
added = worktree_add(repo, "lokay/7", wt)
assert added["result"] == "added", added
env = {"PATH": os.environ["PATH"], "GH_TOKEN": "secret", "GITHUB_TOKEN": "secret", "LOKAY2_PROVIDER": "omniroute", "LOKAY2_MODEL": "m", "PI_ENV": os.environ["PI_ENV"], "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "a@b.c", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "a@b.c"}
done = build_code(wt, "plan", "title", "body", env)
assert done["result"] == "done", done
assert len(done['pi_response']) == 1500
assert done['pi_response'].endswith('Dodano a.py z implementacją.\n')
unchanged = build_code(wt, "re-plan", "title", "body", env, previous_head=done['artifact'])
assert unchanged['reason'] == 'no_changes', unchanged
dumped = Path(os.environ["PI_ENV"]).read_text()
assert "GH_TOKEN" not in dumped and "GITHUB_TOKEN" not in dumped
assert child_env(env).get("GH_TOKEN") is None
plan_path = repo.parent / "plan.md"
plan_path.write_text("body", encoding="utf-8")
state_update('mikolaj92/lokay-sandbox', 7, pi_response=done['pi_response'])
published = build_publish(wt, "lokay/7", None, "mikolaj92/lokay-sandbox", 7, "title", plan_path)
assert published["result"] == "pr_open", published
assert published["sha"] == done["artifact"]
# No new pi commit: publish all eight commits left by earlier attempts.
assert build_code(wt, 'plan', 'title', 'body', env, expected_branch='lokay/7')['reason'] == 'no_changes'
remote_head = published['sha']
for number in range(8):
    (wt / 'pending.py').write_text(f'pending = {number}\n')
    _git(wt, ['add', 'pending.py'])
    _git(wt, ['commit', '-m', f'pending {number}'])
assert _git(wt, ['rev-list', '--count', 'origin/lokay/7..HEAD']) == '8'
recovered = build_code(wt, 'plan', 'title', 'body', env, expected_branch='lokay/7')
assert recovered == {'result': 'done', 'artifact': _git(wt, ['rev-parse', 'HEAD']),
                     'pi_response': done['pi_response']}, recovered
republished = build_publish(wt, 'lokay/7', remote_head, 'mikolaj92/lokay-sandbox', 7, 'title', plan_path)
assert republished['result'] == 'pr_open', republished
assert republished['sha'] == recovered['artifact']
assert _git(wt, ['rev-list', '--count', 'origin/lokay/7..HEAD']) == '0'
assert build_code(wt, 'plan', 'title', 'body', env, expected_branch='lokay/7')['reason'] == 'no_changes'
# A linked worktree stores MERGE_HEAD outside its .git file.
_git(wt, ['checkout', '-b', 'merge-fixture'])
(wt / 'merged.py').write_text('merged = True\n')
_git(wt, ['add', 'merged.py'])
_git(wt, ['commit', '-m', 'merge fixture'])
_git(wt, ['checkout', 'lokay/7'])
_git(wt, ['merge', '--no-ff', '--no-commit', 'merge-fixture'])
(wt / 'partial.py').write_text('partial = True\n')
assert tidy_and_commit(wt, 'partial')[0] == ['partial.py']
assert not (wt / _git(wt, ['rev-parse', '--git-path', 'MERGE_HEAD'])).exists()
assert len(_git(wt, ['rev-list', '--parents', '-n', '1', 'HEAD~1']).split()) == 3
# Conflicted merges are aborted before committing pi's paths.
_git(wt, ['checkout', 'merge-fixture'])
(wt / 'f').write_text('theirs\n')
_git(wt, ['commit', '-am', 'theirs'])
_git(wt, ['checkout', 'lokay/7'])
(wt / 'f').write_text('ours\n')
_git(wt, ['commit', '-am', 'ours'])
try:
    _git(wt, ['merge', '--no-ff', 'merge-fixture'])
except RuntimeError:
    pass
assert _git(wt, ['ls-files', '-u'])
(wt / 'after_abort.py').write_text('recovered = True\n')
assert tidy_and_commit(wt, 'after abort')[0] == ['after_abort.py']
assert (wt / 'f').read_text() == 'ours\n'
assert not (wt / _git(wt, ['rev-parse', '--git-path', 'MERGE_HEAD'])).exists()
log = Path(os.environ['GH_LOG']).read_text()
assert '## Co zrobiono' in log and 'Dodano a.py z implementacją.' in log
assert '- `a.py`' in log and '- `f`' not in log
# Refresh uses the persisted Fix response and the current diff, not the plan.
(wt / 'fixed.py').write_text('fixed = True\n')
__import__('subprocess').run(['git', 'add', 'fixed.py'], cwd=wt, check=True)
__import__('subprocess').run(['git', 'commit', '-m', 'lokay fix'], cwd=wt, check=True, capture_output=True)
repo_name = 'mikolaj92/lokay-sandbox'
state_update(repo_name, 7, pi_response='Dodano fixed.py po Fix.')
(run_dir(repo_name, 7) / 'plan.md').write_text('## Cel\nPlan, nie wynik.\n')
with patch('lokay.start.load_repos', return_value=[{'name': repo_name, 'clone_path': str(repo)}]), \
     patch('lokay.start.open_pr_for', return_value={'number': 1}):
    # The fixture worktree has a shorter name than the runtime convention.
    __import__('subprocess').run(['git', 'worktree', 'move', str(wt), str(repo.parent / f'{repo.name}-wt-7')], cwd=repo, check=True)
    assert refresh_body(repo_name, 7)['result'] == 'updated'
    __import__('subprocess').run(['git', 'worktree', 'move', str(repo.parent / f'{repo.name}-wt-7'), str(wt)], cwd=repo, check=True)
log = Path(os.environ['GH_LOG']).read_text()
assert 'pr edit 1' in log and 'Dodano fixed.py po Fix.' in log
assert '- `a.py`' in log and '- `fixed.py`' in log
assert state_read(repo_name, 7)['pi_response'] == 'Dodano fixed.py po Fix.'
moved = build_publish(wt, "lokay/7", "0"*40, "mikolaj92/lokay-sandbox", 7, "title", plan_path)
assert moved["result"] == "remote_moved", moved
print("pr_open", published["sha"][:12])
print("remote_moved")
PY
rm -rf "$tmp"
