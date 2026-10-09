#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
root=$(mktemp -d)
cat > "$root/gh" <<'EOF'
#!/bin/sh
printf '%s
' "$*" >> "$GH_LOG"
exit 1
EOF
chmod +x "$root/gh"
export GH_LOG="$root/calls"
export PATH="$root:$PATH"
export HOME="$root/home"
mkdir -p "$HOME"
: > "$GH_LOG"
uv run python - <<'PY'
import os
for _ in range(3):
    from lokay2.start import pick
    outcome = pick({"PATH": os.environ["PATH"], "LOKAY2_GB10": "down", "LOKAY2_PROVIDER": "omniroute", "LOKAY2_MODEL": "m", "LOKAY2_DECISION_API": "tensorfold", "LOKAY2_DECISION_MODEL": "m"})
    assert outcome["result"] == "idle" and outcome["reason"] == "host", outcome
    print("host down")
print("writes", open(os.environ["GH_LOG"]).read().count("\n"))
PY
test "$(wc -l < "$GH_LOG" | tr -d ' ')" = "0"
rm -rf "$root"
