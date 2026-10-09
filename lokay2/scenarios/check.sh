#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
uv run python - <<'PY'
from lokay2.check import aggregate, decide_hunks, hunks

diff = """diff --git a/a.py b/a.py
+++ b/a.py
@@ -10,2 +10,3 @@
+    return n + 0
"""
rows = hunks(diff)
assert rows[0]["plik"] == "a.py" and rows[0]["linia_od"] == 10
wire_bad = {
    "model": "m",
    "usage": {"completion_tokens": 0},
    "answers": {
        "next": {"choice": "issue", "probabilities": {"issue": 0.9, "ok": 0.1}},
        "h1": {"choice": "true", "probabilities": {"true": 0.92, "false": 0.08}},
    },
}
bad = decide_hunks("correctness", rows, wire_bad, "m")
assert bad["next"] == "issue", bad
assert bad["uwagi"][0]["plik"] == "a.py" and bad["uwagi"][0]["linia_od"] == 10
wire_ok = {
    "model": "m",
    "usage": {"completion_tokens": 0},
    "answers": {
        "next": {"choice": "ok", "probabilities": {"ok": 0.95, "issue": 0.05}},
        "h1": {"choice": "true", "probabilities": {"true": 0.7, "false": 0.3}},
    },
}
nit = decide_hunks("scope", rows, wire_ok, "m")
assert nit["next"] == "ok" and nit["nits"], nit
merged = aggregate("abc", {"result": "green", "sha": "abc", "failed": []}, [
    {"next": "ok", "sha": "abc", "uwagi": []},
    {"next": "ok", "sha": "abc", "uwagi": []},
    {"next": "ok", "sha": "abc", "uwagi": []},
])
assert merged["result"] == "merge", merged
fixed = aggregate("abc", {"result": "red", "sha": "abc", "failed": [{"warstwa": "unit"}]}, [
    {"next": "ok", "sha": "abc", "uwagi": []},
    {"next": "ok", "sha": "abc", "uwagi": []},
    {"next": "ok", "sha": "abc", "uwagi": []},
])
assert fixed["result"] == "fix"
trap = decide_hunks("tests", [{"plik": "t.py", "linia_od": 1, "linia_do": 2, "body": ["+assert True"]}], {
    "model": "m",
    "usage": {"completion_tokens": 0},
    "answers": {
        "next": {"choice": "issue", "probabilities": {"issue": 0.9, "ok": 0.1}},
        "h1": {"choice": "true", "probabilities": {"true": 0.9, "false": 0.1}},
    },
}, "m")
assert trap["next"] == "issue"
extra = decide_hunks("correctness alignment architecture security production", rows, wire_bad, "m")
assert extra["next"] == "issue" and extra["uwagi"][0]["plik"] == "a.py"
assert extra["next"] in {"ok", "issue"}
healed = aggregate("abc", {"result": "green", "sha": "abc", "failed": []}, [
    {"next": "ok", "sha": "abc", "uwagi": []},
    {"next": "ok", "sha": "abc", "uwagi": []},
    {"next": "ok", "sha": "abc", "uwagi": []},
    extra,
])
assert healed["result"] == "fix" and healed["uwagi"][0]["plik"] == "a.py"
clean = dict(extra, next="ok", uwagi=[])
landed = aggregate("abc", {"result": "green", "sha": "abc", "failed": []}, [
    {"next": "ok", "sha": "abc", "uwagi": []},
    {"next": "ok", "sha": "abc", "uwagi": []},
    {"next": "ok", "sha": "abc", "uwagi": []},
    clean,
])
assert landed["result"] == "merge"
try:
    decide_hunks("scope", rows, {"model": "m", "usage": {"completion_tokens": 0}, "answers": {"next": {"choice": "maybe", "probabilities": {"maybe": 1}}}}, "m")
except Exception:
    pass
else:
    raise SystemExit("maybe accepted")
print("issue", bad["uwagi"][0]["plik"], bad["uwagi"][0]["linia_od"])
print("merge")
PY
