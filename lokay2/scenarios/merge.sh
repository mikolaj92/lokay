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
from lokay2.merge import merge_sha
from lokay2.lock import acquire

home_repo = "mikolaj92/lokay-sandbox"
held = acquire("mikolaj92", home_repo)
got = merge_sha(home_repo, 3, os.environ["SHA"], {"result": "merge", "sha": os.environ["SHA"]}, None, held, "mikolaj92", 3, {"plan_rounds": 1, "check_rounds": 1})
assert got["result"] == "merged", got
log = Path(os.environ["GH_LOG"]).read_text()
assert "--match-head-commit" in log and os.environ["SHA"] in log
moved = merge_sha(home_repo, 3, "other", {"result": "merge", "sha": os.environ["SHA"]}, None, None, "mikolaj92", 3, {})
assert moved["result"] == "sha_moved"
again = acquire("mikolaj92", home_repo)
assert again["result"] == "held"
print("merged")
print("sha_moved")
PY
rm -rf "$tmp"
