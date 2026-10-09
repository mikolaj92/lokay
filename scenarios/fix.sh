#!/bin/sh
set -eu
tmp=$(mktemp -d)
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
bare="$tmp/bare.git"
src="$tmp/src"
git init --bare -b main "$bare" >/dev/null
git clone "$bare" "$src" >/dev/null 2>&1
git -C "$src" config user.email a@b.c
git -C "$src" config user.name t
echo base > "$src/f"
git -C "$src" add f && git -C "$src" commit -m base >/dev/null
git -C "$src" branch lokay/9
git -C "$src" push -u origin main >/dev/null 2>&1
git -C "$src" push -u origin lokay/9 >/dev/null 2>&1
cat > "$tmp/pi" <<'EOF'
#!/bin/sh
echo fixed >> a.py
exit 0
EOF
chmod +x "$tmp/pi"
export PATH="$tmp:$PATH"
uv run python - "$src" <<'PY'
import os, sys
from pathlib import Path
from lokay.fix import fix_code, fix_publish
from lokay.git import worktree_add

repo = Path(sys.argv[1])
wt = repo.parent / "fixwt"
added = worktree_add(repo, "lokay/9b", wt)
assert added["result"] == "added", added
previous = __import__("subprocess").check_output(["git", "rev-parse", "HEAD"], cwd=wt, text=True).strip()
env = {"PATH": os.environ["PATH"], "LOKAY2_PROVIDER": "p", "LOKAY2_MODEL": "m", "GH_TOKEN": "nope", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "a@b.c", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "a@b.c"}
done = fix_code(wt, previous, "uwagi a.py:1", env)
assert done["result"] == "done" and done["artifact"] != previous, done
published = fix_publish(wt, "lokay/9b", None)
assert published["result"] == "pushed", published
assert published["sha"] == done["artifact"]
same = fix_code(wt, done["artifact"], "again", {**env, "PATH": "/usr/bin:/bin"})
# pi missing means failed and sha stays
print("pushed", published["sha"][:12])
PY
rm -rf "$tmp"
