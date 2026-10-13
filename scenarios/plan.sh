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
from lokay.plan import plan_check, plan_write, prompt_for

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
low["answers"]["next"] = {"choice": "revise", "probabilities": {"ok": 0.1, "revise": 0.9}}
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
# Only clear false criteria block; uncertain criteria are non-blocking notes.
for p in (0.349999, 0.35, 0.350001, 0.39, 0.499999, 0.5, 0.85):
    for next_answer in (low['answers']['next'], wire['answers']['next']):
        boundary = json.loads(json.dumps(wire))
        boundary['answers']['next'] = next_answer
        boundary['answers']['k_testy'] = {
            'choice': 'true' if p >= 0.5 else 'false',
            'probabilities': {'true': p, 'false': 1 - p}}
        result = plan_check(boundary, 'm')
        finding = {'kryterium': 'k_testy', 'p': p}
        assert result['next'] == ('revise' if p < 0.35 else 'ok'), result
        assert result['uwagi'] == ([finding] if p < 0.35 else []), result
        assert result['notes'] == ([finding] if 0.35 <= p < 0.5 else []), result
assert plan_check(low, 'm')['next'] == 'revise'
print("plan ok; blocking below 0.35, notes below 0.5, choice alone never blocks")
print(json.dumps(checked))
PY
rm -rf "$root"
