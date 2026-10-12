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
print("legacy contracts ok")
typed_model = "embeddinggemma-2-ft-typed-decision"
typed = json.loads(json.dumps(internal))
typed["workflow"] = "Plan, Build, Check, Fix, Merge"
typed["questions"].append({"id": "quality", "type": "score", "instructions": "quality",
                           "options": {"low": "needs work", "high": "ready"}})
typed_payload = {
    "next": {"kind": "choice", "label": "ok", "value": "ok", "confidence": 0.9,
             "probabilities": {"ok": 0.9, "revise": 0.1}, "expected_level": None},
    "k_cel": {"kind": "noul", "label": "true", "value": True, "confidence": 0.91,
              "probabilities": {"false": 0.09, "true": 0.91}, "expected_level": None},
    "quality": {"kind": "score", "label": "1", "value": 1, "confidence": 0.8,
                "probabilities": {"0": 0.2, "1": 0.8}, "expected_level": 0.8},
}
wire = to_wire("typed-decisions", typed_model, typed)
assert set(wire) == {"workflow", "state", "questions"}, wire
assert wire["workflow"] == typed["workflow"]
assert wire["questions"]["next"]["criteria"] == {"ok": "ship", "revise": "again"}
assert wire["questions"]["k_cel"] == {"type": "noul", "instructions": "covers goal"}
assert wire["questions"]["quality"]["criteria"] == {"0": "low: needs work", "1": "high: ready"}
typed_expected = {**expected, "quality": {"choice": "high", "probabilities": {"low": 0.2, "high": 0.8}, "confidence": 0.8}}
assert from_wire("typed-decisions", typed_model, typed_payload, typed) == typed_expected
# Exercise the real curl transport against an independent HTTP protocol fixture.
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch
from lokay.decide import decide
class API(BaseHTTPRequestHandler):
    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        valid = (self.path == "/v1/decisions" and request == wire
                 and self.headers.get("Authorization") == "Bearer scenario-key")
        self.send_response(200 if valid else 422)
        self.end_headers()
        self.wfile.write(json.dumps(typed_payload if valid else {}).encode())
    def log_message(self, *args):
        pass
server = HTTPServer(("127.0.0.1", 0), API)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    with patch.dict(os.environ, {"LOKAY2_DECISION_API": "typed-decisions",
                    "LOKAY2_DECISION_MODEL": typed_model,
                    "LOKAY2_DECISION_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                    "LOKAY2_DECISION_API_KEY": "scenario-key"}):
        assert decide(typed) == typed_expected
finally:
    server.shutdown()
    thread.join()
    server.server_close()
print("typed-decisions choice/bool/score HTTP contract ok")
# Numeric score levels retain their values, not their insertion indices.
numeric = {"state": {}, "questions": [{"id": "level", "type": "score",
           "instructions": "level", "options": {"-2": "poor", "5": "good"}}]}
assert to_wire("typed-decisions", typed_model, numeric)["questions"]["level"]["criteria"] == numeric["questions"][0]["options"]
assert from_wire("typed-decisions", typed_model, {"level": {
    "kind": "score", "label": "5", "value": 5, "confidence": 0.7,
    "probabilities": {"-2": 0.3, "5": 0.7}, "expected_level": 2.9}}, numeric)["level"]["choice"] == "5"
false_payload = json.loads(json.dumps(typed_payload))
false_payload["k_cel"].update(label="false", value=False, confidence=0.91,
                            probabilities={"false": 0.91, "true": 0.09})
assert from_wire("typed-decisions", typed_model, false_payload, typed)["k_cel"]["choice"] == "false"
for name, qid, field, value in [
    ("kind", "k_cel", "kind", "choice"),
    ("value", "k_cel", "value", "true"),
    ("label", "next", "label", "ship"),
    ("argmax", "next", "probabilities", {"ok": 0.1, "revise": 0.9}),
    ("sum", "next", "probabilities", {"ok": 0.2, "revise": 0.2}),
    ("options", "quality", "probabilities", {"low": 0.2, "high": 0.8}),
    ("nonfinite", "next", "probabilities", {"ok": float("nan"), "revise": 0.1}),
    ("range", "next", "probabilities", {"ok": 1.1, "revise": -0.1}),
    ("confidence", "next", "confidence", None),
]:
    bad = json.loads(json.dumps(typed_payload))
    bad[qid][field] = value
    try:
        from_wire("typed-decisions", typed_model, bad, typed)
    except DecisionError:
        pass
    else:
        raise AssertionError(f"accepted typed {name}")
for bad in ({"answers": typed_payload}, {"next": typed_payload["next"]}):
    try:
        from_wire("typed-decisions", typed_model, bad, typed)
    except DecisionError:
        pass
    else:
        raise AssertionError("accepted wrapped/missing typed answers")
print("typed numeric levels, false predicate and malformed answers ok")
large = {
    "state": {"plan": "x" * 10000, "nested": ["ż\\\"" * 5000, {"log": "y" * 10000}]},
    "questions": [{"id": "up", "type": "bool", "instructions": "z" * 1000,
                   "options": {"true": "yes", "false": "no"}}],
}
for api in ("tensorfold", "openai-decisions", "systemone", "typed-decisions"):
    wire = to_wire(api, model, large)
    assert len(json.dumps(wire)) < 6000, api
    state = wire.get("input", wire.get("state"))
    assert len(state["plan"]) <= 3000
    assert len(state["nested"][0]) <= 3000
    assert len(state["nested"][1]["log"]) <= 3000
    question = wire["questions"]["up"] if api in ("systemone", "typed-decisions") else wire["questions"][0]
    assert len(question.get("question", question.get("instructions"))) == 600
assert len(large["state"]["plan"]) == 10000
print("request character limits ok")
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
