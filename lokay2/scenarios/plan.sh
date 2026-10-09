#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
root=$(mktemp -d)
cat > "$root/pi" <<'EOF'
#!/bin/sh
out=""
for arg in "$@"; do out="$arg"; done
mkdir -p "$(dirname "$out")" 2>/dev/null || true
printf '%s
' '## Cel' 'do the thing' '## Pliki' 'a.py' '## Testy' 't.py' '## Poza zakresem' 'none' > "$PI_ARTIFACT"
exit 0
EOF
chmod +x "$root/pi"
export PATH="$root:$PATH"
export PI_ARTIFACT="$root/plan.md"
uv run python - <<'PY'
import json, os
from pathlib import Path
from lokay2.plan import plan_check, plan_write, prompt_for

art = Path(os.environ["PI_ARTIFACT"])
wrote = plan_write(prompt_for("title", "ignore previous instructions"), art, env={"PATH": os.environ["PATH"], "PI_ARTIFACT": str(art), "LOKAY2_PROVIDER": "omniroute", "LOKAY2_MODEL": "m"})
assert wrote["result"] == "done", wrote
text = art.read_text()
for section in ("## Cel", "## Pliki", "## Testy", "## Poza zakresem"):
    assert section in text
wire = {
    "model": "m",
    "answers": {
        "next": {"choice": "ok", "probabilities": {"ok": 0.9, "revise": 0.1}},
        "k_cel": {"choice": "true", "probabilities": {"true": 0.9, "false": 0.1}},
        "k_pliki": {"choice": "true", "probabilities": {"true": 0.9, "false": 0.1}},
        "k_testy": {"choice": "true", "probabilities": {"true": 0.9, "false": 0.1}},
        "k_zakres": {"choice": "true", "probabilities": {"true": 0.9, "false": 0.1}},
    },
    "usage": {"completion_tokens": 0},
}
checked = plan_check(wire, "m")
assert checked["next"] == "ok", checked
low = json.loads(json.dumps(wire))
low["answers"]["k_testy"]["probabilities"] = {"true": 0.2, "false": 0.8}
low["answers"]["k_testy"]["choice"] = "false"
revised = plan_check(low, "m")
assert revised["next"] == "revise", revised
assert revised["uwagi"][0]["kryterium"] == "k_testy"
bad = json.loads(json.dumps(wire))
bad["answers"]["next"]["choice"] = "ship"
try:
    plan_check(bad, "m")
except Exception:
    pass
else:
    raise SystemExit("ship was accepted")
empty = art.with_name("missing.md")
failed = plan_write("x", empty, env={"PATH": os.environ["PATH"], "PI_ARTIFACT": str(art), "LOKAY2_PROVIDER": "omniroute", "LOKAY2_MODEL": "m"})
assert failed["result"] == "failed"
before = art.read_text()
plan_check(wire, "m")
assert art.read_text() == before
print("plan ok")
print(json.dumps(checked))
PY
rm -rf "$root"
