#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
uv run python - <<'PY'
import json
from pathlib import Path
from lokay.decide import DecisionError, from_wire, to_wire

root = Path("fixtures/decisions")
internal = json.loads((root / "internal_request.json").read_text())
expected = json.loads((root / "internal_response.json").read_text())
model = "GLM-5.3-Flash-EXL3"
for api in ("tensorfold", "openai-decisions", "systemone"):
    wire = to_wire(api, model, internal)
    payload = json.loads((root / api / "response.json").read_text())
    got = from_wire(api, model, payload, internal)
    assert got == expected, (api, got)
    assert wire["model"] == model
print("contract ok")
tf = json.loads((root / "tensorfold" / "response.json").read_text())
cases = []
missing = json.loads(json.dumps(tf)); del missing["answers"]["k_cel"]; cases.append(missing)
choice = json.loads(json.dumps(tf)); choice["answers"]["next"]["choice"] = "ship"; cases.append(choice)
total = json.loads(json.dumps(tf)); total["answers"]["next"]["probabilities"] = {"ok": 0.2, "revise": 0.2}; cases.append(total)
other = json.loads(json.dumps(tf)); other["model"] = "other"; cases.append(other)
tokens = json.loads(json.dumps(tf)); tokens["usage"]["completion_tokens"] = 3; cases.append(tokens)
for payload in cases:
    try:
        from_wire("tensorfold", model, payload, internal)
    except DecisionError:
        continue
    raise SystemExit("accepted bad payload")
print("bad fixtures rejected")
PY
wc -l src/lokay/decide.py
