#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
root=$(mktemp -d)
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
  if [ "${OPEN_PR:-}" = "yes" ]; then
    printf '%s\n' '[{"number":10,"headRefName":"lokay/2","headRefOid":"abc"}]'
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
assert pick({**env, "LOKAY2_REPO": "example/untested"}) == {"result": "idle", "reason": "no_work"}
assert "example/untested" not in open(os.environ["GH_LOG"]).read()
got = pick(env)
assert got["issue"] == 1 and got["node"] == "plan" and got["repo"] == "example/first", got
assert pick({**env, "LOKAY2_REPO": "example/first"}) == {"result": "idle", "reason": "no_work"}
start.release(got["held"])
start.release(got["held"])
os.environ["OPEN_PR"] = "yes"
got = pick({**env, "LOKAY2_REPO": "example/second", "LOKAY2_ISSUE": "2"})
assert got["repo"] == "example/second" and got["issue"] == 2 and got["node"] == "check" and got["pr"] == 10, got
start.release(got["held"])
assert pick({**env, "LOKAY2_ISSUE": "3"}) == {"result": "idle", "reason": "no_work"}
assert pick({**env, "LOKAY2_REPO": "example/missing"}) == {"result": "idle", "reason": "no_work"}
assert "--label" not in open(os.environ["GH_LOG"]).read()
print("pick: oldest, tie-break, Epic, overrides, open PR OK")
PY
rm -rf "$root"
