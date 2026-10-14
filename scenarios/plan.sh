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
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from lokay.plan import plan_check, plan_write, prompt_for, render_synthesis, synthesize, validate_synthesis

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
# Synthesis uses only accepted branches, including sources in extra fields.
accepted = {"minimal", "gates"}
synthesis = {
    "cel": "Ship the smallest safe change",
    "kryteria": [{"tresc": "Scenario passes", "zrodla": ["gates"]}],
    "kroki": [{"tresc": "Update implementation", "zrodla": ["minimal", "gates"]}],
    "pliki": [{"sciezka": "a.py", "zmiana": "Validate input", "zrodla": ["minimal"]}],
    "testy": [{"tresc": "Run scenario", "zrodla": ["gates"]}],
    "poza_zakresem": [{"tresc": "New dependencies", "zrodla": ["minimal"]}],
    "odrzucone": [{"tresc": "Add a framework", "zrodlo": "risk", "powod": "Unnecessary"}],
}
assert validate_synthesis(synthesis, accepted) == synthesis
rendered = render_synthesis(synthesis)
for fragment in (
    "## Cel\nShip the smallest safe change", "### Kryteria\n- Scenario passes [źródła: gates]",
    "### Kroki\n- Update implementation [źródła: minimal, gates]",
    "## Pliki\n- a.py: Validate input [źródła: minimal]",
    "## Testy\n- Run scenario [źródła: gates]",
    "## Poza zakresem\n- New dependencies [źródła: minimal]",
    "### Odrzucone\n- Add a framework [risk]: Unnecessary",
):
    assert fragment in rendered, rendered

rejected_count = 0
def reject(data):
    global rejected_count
    try:
        validate_synthesis(data, accepted)
    except ValueError:
        rejected_count += 1
    else:
        raise AssertionError(f"Invalid synthesis accepted: {data!r}")

for value in (None, [], "plan"):
    reject(value)
for field in synthesis:
    bad = deepcopy(synthesis)
    del bad[field]
    reject(bad)
    for value in ((None, 42, [], {}) if field == "cel" else (None, "rows", {})):
        bad = deepcopy(synthesis)
        bad[field] = value
        reject(bad)
for field in synthesis.keys() - {"cel"}:
    for value in (None, "row", []):
        bad = deepcopy(synthesis)
        bad[field] = [value]
        reject(bad)
    for name in synthesis[field][0]:
        bad = deepcopy(synthesis)
        del bad[field][0][name]
        reject(bad)
        if name not in ("zrodla", "zrodlo"):
            for value in (None, 42, [], {}):
                bad = deepcopy(synthesis)
                bad[field][0][name] = value
                reject(bad)
    if field != "odrzucone":
        for sources in (None, "minimal", {}, [], ["unknown"], ["risk"], [42], ["minimal", "risk"]):
            bad = deepcopy(synthesis)
            bad[field][0]["zrodla"] = sources
            reject(bad)
for source in (None, 42, [], {}, "unknown"):
    bad = deepcopy(synthesis)
    bad["odrzucone"][0]["zrodlo"] = source
    reject(bad)
for sources in ([], ["unknown"], ["risk"]):
    bad = deepcopy(synthesis)
    bad["extra"] = {"nested": [{"zrodla": sources}]}
    reject(bad)

# Exercise JSON parsing through the synthesis step, not only the validator.
def invalid_json_step(prompt, artifact):
    assert not artifact.exists(), "Stale synthesis artifact survived"
    artifact.write_text("{invalid JSON")
    return {"result": "done", "artifact": str(artifact)}

json_art = art.with_name("synthesis.json")
json_art.write_text(json.dumps(synthesis))
before = art.read_text()
with patch("lokay.plan.pi_step", side_effect=invalid_json_step) as stub:
    failed = synthesize({"minimal": art}, "issue", art)
    assert failed["result"] == "failed", failed
    assert "invalid synthesis" in failed["reason"], failed
    assert art.read_text() == before
    assert stub.call_count == 1

# A successful pi exit without a fresh write must not reuse a valid old plan.
assert all(section in art.read_text() for section in ("## Cel", "## Pliki", "## Testy", "## Poza zakresem"))
def no_write_step(prompt, artifact, **kwargs):
    assert not artifact.exists(), "Stale plan artifact survived"
    return {"result": "done", "artifact": str(artifact)}

with patch("lokay.plan.pi_step", side_effect=no_write_step) as stub:
    failed = plan_write("x", art)
    assert failed == {"result": "failed", "artifact": ""}, failed
    assert not art.exists()
    assert stub.call_count == 1
print(f"synthesis ok; valid render, {rejected_count} schema rejections, invalid JSON, stale plan rejected")
print("plan ok; blocking below 0.35, notes below 0.5, choice alone never blocks")
print(json.dumps(checked))
PY
rm -rf "$root"
