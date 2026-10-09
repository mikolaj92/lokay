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
' '[{"number":2,"createdAt":"2026-10-09T02:00:00Z","title":"b"},{"number":1,"createdAt":"2026-10-09T01:00:00Z","title":"a"}]'
  exit 0
fi
if [ "$1" = "pr" ]; then
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
export GH_LOG="$root/calls"
export PATH="$root:$PATH"
export HOME="$root/home"
mkdir -p "$HOME"
: > "$GH_LOG"
uv run python - <<'PY'
import os
from lokay.start import pick
env = {
    "PATH": os.environ["PATH"],
    "HOME": os.environ["HOME"],
    "LOKAY2_GB10": "up",
    "LOKAY2_PROVIDER": "omniroute",
    "LOKAY2_MODEL": "m",
    "LOKAY2_DECISION_API": "tensorfold",
    "LOKAY2_DECISION_MODEL": "m",
}
got = pick(env)
assert got["issue"] == 1 and got["node"] == "plan", got
print("picked", got["issue"])
PY
rm -rf "$root"
