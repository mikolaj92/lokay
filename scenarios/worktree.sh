#!/bin/sh
set -eu
root=$(mktemp -d)
bare="$root/bare.git"
src="$root/src"
wt="$root/wt/issue"
git init --bare -b main "$bare" >/dev/null
git clone "$bare" "$src" >/dev/null 2>&1
git -C "$src" config user.email a@b.c
git -C "$src" config user.name t
echo one > "$src/f"
git -C "$src" add f && git -C "$src" commit -m one >/dev/null
git -C "$src" push -u origin main >/dev/null 2>&1
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
uv run python - "$src" "$wt" <<'PY'
import sys
from pathlib import Path
from lokay.git import reap_worktrees, worktree_add, worktree_remove
from lokay.run import run_process

repo, path = Path(sys.argv[1]), Path(sys.argv[2])
added = worktree_add(repo, "lokay/1", path)
assert added["result"] == "added", added
again = worktree_add(repo, "lokay/1", path)
assert "already" in again.get("error", "") or again["result"] == "added", again
listed = run_process(["git", "worktree", "list"], cwd=repo)
assert "lokay/1" in (listed.stdout or ""), listed.stdout
removed = worktree_remove(repo, path)
assert removed["result"] == "removed", removed
listed = run_process(["git", "worktree", "list"], cwd=repo)
assert "lokay/1" not in (listed.stdout or ""), listed.stdout
stale = path.parent / "old"
added = worktree_add(repo, "lokay/old", stale)
assert added["result"] == "added", added
old = stale.stat().st_mtime
reap_worktrees(repo, path.parent, ttl_seconds=10, now=old + 30)
listed = run_process(["git", "worktree", "list"], cwd=repo)
assert "lokay/old" not in (listed.stdout or ""), listed.stdout
# A removed sandbox worktree is recreated in the very next resume tick.
import shutil
import tempfile
from unittest.mock import patch
from lokay import start, state
issue_path = repo.parent / f"{repo.name}-wt-1"
assert run_process(['git', 'worktree', 'add', str(issue_path), 'lokay/1'], cwd=repo).returncode == 0
run_process(['git', 'push', 'origin', 'lokay/1'], cwd=issue_path)
sha = run_process(['git', 'rev-parse', 'HEAD'], cwd=issue_path).stdout.strip()
shutil.rmtree(issue_path)
picked = {'repo': 'example/sandbox', 'issue': 1, 'pr': 1, 'node': 'check'}
with tempfile.TemporaryDirectory() as runs, \
     patch.object(state, 'RUNS', Path(runs)), \
     patch('lokay.start.load_repos', return_value=[{'name': picked['repo'], 'clone_path': str(repo), 'test': []}]), \
     patch('lokay.start.open_pr_for', return_value={'number': 1, 'headRefOid': sha}), \
     patch('lokay.start._finish', return_value={'result': 'pending'}) as finish:
    assert start.resume(picked)['result'] == 'pending'
    assert issue_path.is_dir()
    assert run_process(['git', 'branch', '--show-current'], cwd=issue_path).stdout.strip() == 'lokay/1'
    finish.assert_called_once()
    # Wrong branch and dirty files survive recovery in a sibling worktree.
    run_process(['git', 'switch', '-c', 'user/other'], cwd=issue_path)
    (issue_path / 'untracked.txt').write_text('keep')
    assert start.resume(picked)['result'] == 'pending'
    backups = list(repo.parent.glob(f'{issue_path.name}-recovery-*'))
    assert len(backups) == 1 and (backups[0] / 'untracked.txt').read_text() == 'keep'
    assert run_process(['git', 'branch', '--show-current'], cwd=backups[0]).stdout.strip() == 'user/other'
    assert run_process(['git', 'rev-parse', 'HEAD'], cwd=issue_path).stdout.strip() == sha
print("worktree: add/remove, next-tick restore and preserved mismatched worktree OK")
PY
rm -rf "$root"
