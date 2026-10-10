#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
tmp=$(mktemp -d)
bare="$tmp/bare.git"
src="$tmp/src"
outside="$tmp/outside"
git init --bare -b main "$bare" >/dev/null
git clone "$bare" "$src" >/dev/null 2>&1
git -C "$src" config user.email a@b.c
git -C "$src" config user.name t
echo base > "$src/f"
git -C "$src" add f && git -C "$src" commit -m base >/dev/null
git -C "$src" push -u origin main >/dev/null 2>&1
git clone "$bare" "$outside" >/dev/null 2>&1
git -C "$outside" config user.email a@b.c
git -C "$outside" config user.name t
echo wandered > "$outside/f"
git -C "$outside" add f && git -C "$outside" commit -m wandered >/dev/null
cat > "$tmp/pi" <<EOF
#!/bin/sh
echo again >> "$outside/f"
git -C "$outside" add f
git -C "$outside" commit -m 'outside commit' >/dev/null
exit 0
EOF
chmod +x "$tmp/pi"
export PATH="$tmp:$PATH"
uv run python - "$src" "$outside" <<'PY'
import os
import sys
from pathlib import Path
from lokay.build import build_code
from lokay.git import worktree_add

repo = Path(sys.argv[1])
outside = Path(sys.argv[2])
wt = repo.parent / "wt"
added = worktree_add(repo, "lokay/7", wt)
assert added["result"] == "added", added
before = __import__("subprocess").check_output(["git", "rev-parse", "HEAD"], cwd=wt, text=True).strip()
outside_before = __import__("subprocess").check_output(["git", "rev-parse", "HEAD"], cwd=outside, text=True).strip()
env = {
    "PATH": os.environ["PATH"],
    "LOKAY2_PROVIDER": "omniroute",
    "LOKAY2_MODEL": "m",
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "a@b.c",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "a@b.c",
}
done = build_code(wt, "plan", "title", None, env, expected_branch="lokay/7")
assert done["result"] == "failed", done
assert done["reason"] == "outside_worktree", done
assert done["explanation"].strip(), done
assert set(done) != {"result", "artifact"}, done
after = __import__("subprocess").check_output(["git", "rev-parse", "HEAD"], cwd=wt, text=True).strip()
assert after == before, (before, after)
outside_after = __import__("subprocess").check_output(["git", "rev-parse", "HEAD"], cwd=outside, text=True).strip()
assert outside_after != outside_before
log = __import__("subprocess").check_output(["git", "log", "--oneline", "origin/main..HEAD"], cwd=wt, text=True)
assert log.strip() == "", log
print("outside_worktree", done["explanation"])
print("worktree unchanged", after)
PY
home="$tmp/home"
mkdir -p "$home"
export HOME="$home"
cat > "$tmp/gh" <<'EOF'
#!/bin/sh
if [ "$1" = "auth" ]; then exit 0; fi
if [ "$1" = "issue" ]; then
  printf '%s\n' '[{"number":2,"createdAt":"2026-10-09T02:00:00Z","title":"b"},{"number":1,"createdAt":"2026-10-09T01:00:00Z","title":"a"}]'
  exit 0
fi
if [ "$1" = "pr" ]; then
  printf '%s\n' '[]'
  exit 0
fi
exit 0
EOF
chmod +x "$tmp/gh"
export PATH="$tmp:$PATH"
uv run python - <<'PY'
import os
from lokay.start import pick, remember_skip

env = {
    "PATH": os.environ["PATH"],
    "HOME": os.environ["HOME"],
    "LOKAY2_GB10": "up",
    "LOKAY2_PROVIDER": "omniroute",
    "LOKAY2_MODEL": "m",
    "LOKAY2_DECISION_API": "tensorfold",
    "LOKAY2_DECISION_MODEL": "m",
}
remember_skip("mikolaj92/lokay-sandbox", 1, "commit is outside the issue worktree")
got = pick(env)
assert got.get("issue") != 1, got
assert got.get("issue") == 2, got
assert got.get("repo") == "mikolaj92/lokay-sandbox", got
print("pick skipped", 1, "selected", got["issue"])
PY
rm -rf "$tmp"
