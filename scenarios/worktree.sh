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
print("worktree ok")
PY
rm -rf "$root"
