#!/bin/sh
set -eu
root=$(mktemp -d)
bare="$root/bare.git"
src="$root/src"
other="$root/other"
git init --bare -b main "$bare" >/dev/null
git clone "$bare" "$src" >/dev/null 2>&1
git -C "$src" config user.email a@b.c
git -C "$src" config user.name t
echo one > "$src/f"
git -C "$src" add f && git -C "$src" commit -m one >/dev/null
git -C "$src" push -u origin main >/dev/null 2>&1
git -C "$src" checkout -b lokay/1 >/dev/null
echo feature > "$src/f"
git -C "$src" commit -am feature >/dev/null
base=$(git -C "$src" rev-parse HEAD)
git clone "$bare" "$other" >/dev/null 2>&1
git -C "$other" config user.email a@b.c
git -C "$other" config user.name t
git -C "$other" checkout -b lokay/1 >/dev/null 2>&1
echo foreign > "$other/f"
git -C "$other" commit -am foreign >/dev/null
git -C "$other" push -u origin lokay/1 >/dev/null 2>&1
remote=$(git -C "$other" rev-parse HEAD)
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
uv run python - "$src" "$base" "$remote" <<'PY'
import sys
from pathlib import Path
from lokay.git import push

repo = Path(sys.argv[1])
expected, remote = sys.argv[2], sys.argv[3]
moved = push(repo, "lokay/1", expected)
assert moved["result"] == "remote_moved", moved
assert moved["sha"] == remote, (moved, remote)
after = __import__("subprocess").check_output(["git", "ls-remote", "origin", "refs/heads/lokay/1"], cwd=repo, text=True).split()[0]
assert after == remote, after
print("remote_moved")

print("push ok")
PY
if grep -R -n -E 'push[^\n]*--force|push[^\n]* -f' "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)/src" --include='*.py'; then
  echo "force push present" >&2
  exit 1
fi
uv run python - "$src" <<'PY'
import subprocess
import sys
from pathlib import Path
from lokay.git import push

repo = Path(sys.argv[1])
before = subprocess.check_output(["git", "rev-parse", "main"], cwd=repo, text=True).strip()
for bad in ("HEAD:main", "+HEAD:main", "refs/heads/main", "main", "master"):
    outcome = push(repo, bad, None)
    if outcome.get("result") != "failed":
        raise SystemExit(f"allowed {bad}: {outcome}")
    print("rejected", bad)
after = subprocess.check_output(["git", "rev-parse", "main"], cwd=repo, text=True).strip()
if after != before:
    raise SystemExit(f"main moved {before} -> {after}")
print("main unchanged")
PY
rm -rf "$root"