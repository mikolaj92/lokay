#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
uv run python - <<'PY'
from lokay.check import aggregate, decide_hunks, hunks

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
# A global issue without a concrete finding returns to Plan.
from copy import deepcopy
from lokay.check import QUESTIONS, lens, questions
import json

kinds = 'correctness alignment architecture security production scope tests'
for kind in kinds.split():
    data = json.loads((QUESTIONS / f'check_{kind}.json').read_text())
    assert set(data) == {'id', 'type', 'question', 'veto'}, data
    assert data['id'] == kind and data['type'] == 'bool' and data['veto'] == 0.85
    assert len(data['question']) > len(kind)
    if kind == 'tests':
        assert 'not evidence of success' in data['question']
    for question in questions(kinds, rows)['questions']:
        assert data['question'] in question['instructions']
from lokay.decide import to_wire
for api in ('tensorfold', 'openai-decisions', 'mini', 'systemone'):
    wire_text = json.dumps(to_wire(api, 'm', questions(kinds, rows)))
    for kind in kinds.split():
        assert lens(kind) in wire_text, (api, kind)
    assert 'a.py:10-12' in wire_text, api
for confidence in (0.84, 0.85, 0.86):
    for choice in ('ok', 'issue'):
        wire = deepcopy(wire_ok)
        wire['answers']['next'] = {'choice': choice, 'probabilities': {
            choice: confidence, ('issue' if choice == 'ok' else 'ok'): 1 - confidence}}
        verdict = decide_hunks(kinds, rows, wire, 'm')
        assert verdict['uwagi'] == []
        assert verdict['next'] == choice, (confidence, choice, verdict)
        assert aggregate('abc', {'result': 'green', 'sha': 'abc'}, [verdict])['result'] == ('plan' if choice == 'issue' else 'merge')
for probability in (0.84, 0.85, 0.86):
    wire = deepcopy(wire_ok)
    wire['answers']['h1'] = {'choice': 'true', 'probabilities': {
        'true': probability, 'false': 1 - probability}}
    verdict = decide_hunks(kinds, rows, wire, 'm')
    assert bool(verdict['uwagi']) == (probability >= 0.85)
    assert verdict['next'] == ('issue' if probability >= 0.85 else 'ok')
try:
    lens('missing-lens')
except FileNotFoundError:
    pass
else:
    raise AssertionError('missing questions accepted')
from dataclasses import replace
from pathlib import Path
from lokay.checks import CheckInput, ci_green, docs, local_tests

input = CheckInput('example/repo', 1865, 'abc', '', '', '', '', [],
                   {'sha': 'abc', 'ci': 'green', 'result': 'green', 'tested': True, 'failed': []}, Path.cwd())
assert ci_green(input)['pass'] and local_tests(input)['pass']
for status in ('red', 'pending', 'no_ci', None):
    assert not ci_green(replace(input, ci={**input.ci, 'ci': status}))['pass']
assert not ci_green(replace(input, ci={**input.ci, 'sha': 'old'}))['pass']
for tested in (False, None, 1):
    assert not local_tests(replace(input, ci={**input.ci, 'tested': tested}))['pass']
assert not local_tests(replace(input, ci={**input.ci, 'result': 'red'}))['pass']
assert not local_tests(replace(input, ci={**input.ci, 'result': 'pending'}))['pass']
github = {'warstwa': 'GitHub CI', 'plik': '.github/workflows/ci.yml', 'linia': 12,
          'log': 'discard-github' + 'G' * 3000}
combined = replace(input, ci={**input.ci, 'ci': 'red', 'result': 'red', 'failed': [github]})
assert local_tests(combined)['pass'] and not ci_green(combined)['pass']
finding = ci_green(combined)
assert finding['location'] == '.github/workflows/ci.yml:12'
assert 'G' * 3000 in finding['reason'] and 'G' * 3000 in finding['fix_hint']
assert 'discard-github' not in finding['reason'] + finding['fix_hint']
local = {'warstwa': 'uv run pytest', 'plik': 'a.py', 'linia': 10,
         'log': 'discard-local' + 'L' * 800}
combined = replace(combined, ci={**combined.ci, 'failed': [github, local]})
finding = local_tests(combined)
assert not finding['pass'] and finding['location'] == 'a.py:10'
assert 'L' * 800 in finding['reason'] and 'L' * 800 in finding['fix_hint']
assert 'discard-local' not in finding['reason'] + finding['fix_hint']
assert 'G' * 800 not in finding['reason'] + finding['fix_hint']
assert not local_tests(replace(input, ci={**input.ci, 'failed': [local]}))['pass']
assert not local_tests(replace(input, ci={**input.ci, 'result': None}))['pass']

doc_diff = 'diff --git a/README.md b/README.md\n+++ b/README.md\n@@ -0,0 +1 @@\n+guide\n'
doc_input = replace(input, diff=doc_diff, plan='Update `README.md`.')
assert not docs(doc_input)['pass']
for request in ('README', 'docs', 'dokumentacja', 'dokumentacji', 'documentation'):
    assert docs(replace(doc_input, issue_title=request))['pass'], request
    assert docs(replace(doc_input, issue_body=request))['pass'], request
for request in ('documentary', 'undocumented', 'readmeish'):
    assert not docs(replace(doc_input, issue_title=request))['pass'], request
for plan in ('', 'other/README.md', 'README.md.old', 'README.md/extra', 'prefix-README.md'):
    assert not docs(replace(doc_input, issue_title='docs', plan=plan))['pass'], plan
second_doc = 'diff --git a/docs/guide.md b/docs/guide.md\n+++ b/docs/guide.md\n@@ -1 +1 @@\n-old\n+new\n'
multiple_docs = replace(doc_input, issue_title='docs', diff=doc_diff + second_doc)
assert not docs(multiple_docs)['pass']
assert docs(replace(multiple_docs, plan='README.md and docs/guide.md'))['pass']
assert docs(replace(doc_input, diff=doc_diff.replace('+guide', '-guide')))['pass']
print('checks: CI SHA/status, local evidence/logs, explicit planned documentation OK')
print("issue", bad["uwagi"][0]["plik"], bad["uwagi"][0]["linia_od"])
print("merge")
PY
