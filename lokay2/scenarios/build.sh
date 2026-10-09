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
: > "$GH_LOG"
uv run python - "$src" <<'PY'
import os, sys
from pathlib import Path
from lokay2.build import build_code, build_publish, child_env

repo = Path(sys.argv[1])
wt = repo.parent / "wt"
from lokay2.git import worktree_add
added = worktree_add(repo, "lokay/7", wt)
assert added["result"] == "added", added
env = {"PATH": os.environ["PATH"], "GH_TOKEN": "secret", "GITHUB_TOKEN": "secret", "LOKAY2_PROVIDER": "omniroute", "LOKAY2_MODEL": "m", "PI_ENV": os.environ["PI_ENV"], "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "a@b.c", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "a@b.c"}
done = build_code(wt, "plan", "title", "body", env)
assert done["result"] == "done", done
dumped = Path(os.environ["PI_ENV"]).read_text()
assert "GH_TOKEN" not in dumped and "GITHUB_TOKEN" not in dumped
assert child_env(env).get("GH_TOKEN") is None
published = build_publish(wt, "lokay/7", None, "mikolaj92/lokay-sandbox", 7, "title")
assert published["result"] == "pr_open", published
assert published["sha"] == done["artifact"]
moved = build_publish(wt, "lokay/7", "0"*40, "mikolaj92/lokay-sandbox", 7, "title")
assert moved["result"] == "remote_moved", moved
print("pr_open", published["sha"][:12])
print("remote_moved")
PY
rm -rf "$tmp"
