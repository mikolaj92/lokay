#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
root=$(mktemp -d)
bin="$root/bin"
mkdir -p "$bin"
cat > "$bin/gh" <<'EOF'
#!/bin/sh
printf '%s
' "$*" >> "$GH_LOG"
if [ "$1" = "pr" ] && [ "$2" = "merge" ]; then
  echo "merge refused: head does not match" >&2
  exit 1
fi
if [ "$1" = "issue" ] && [ "$2" = "list" ]; then
  case " $* " in
    *" --label "*) printf '%s
' '[]' ;;
    *) printf '%s
' '[{"number":2,"createdAt":"2026-10-09T00:00:02Z","title":"new"},{"number":1,"createdAt":"2026-10-09T00:00:01Z","title":"old"}]' ;;
  esac
  exit 0
fi
exit 0
EOF
chmod +x "$bin/gh"
export PATH="$bin:$PATH"
export GH_LOG="$root/gh.log"
touch "$GH_LOG"
uv run python - <<'PY'
import os
from pathlib import Path
from lokay.gh import issues_with_label, merge, pr_create

rows = issues_with_label("mikolaj92/lokay-sandbox")
assert [row["number"] for row in rows] == [1, 2], rows
assert issues_with_label("mikolaj92/lokay-sandbox", "lokaj") == []
moved = merge("mikolaj92/lokay-sandbox", 9, "abc")
assert moved["result"] == "sha_moved", moved
log = Path(os.environ["GH_LOG"]).read_text()
assert "--admin" not in log
assert "--match-head-commit" in log
body = pr_create("mikolaj92/lokay-sandbox", "lokay/1", "t", "plan", 1)
assert body["result"] == "pr_open"
log = Path(os.environ["GH_LOG"]).read_text()
assert "Closes #1" in log
assert "Opened by lokay" in log
print("sha_moved")
print("merge guard ok")
PY
rm -rf "$root"
