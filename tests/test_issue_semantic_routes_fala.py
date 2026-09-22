"""#1172: native triage producers, not prose, authorize sieve effects."""

import json

import pytest
from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def run_triage(tmp_path, *, title, body, verdict="ready", reason="documentation_only", state="OPEN", covering=None):
    tmp_path.mkdir(exist_ok=True)
    config = tmp_path / "config.yaml"
    config.write_text("repos: []\nstate:\n  path: " + str(tmp_path / "state.json") + "\n")
    issue = {"repo": "o/r", "number": 1172, "title": title, "body": body,
             "state": state, "labels": [], "assignees": []}
    script = base_effector(f"""from lokay.organ.common import _conduction_values
from lokay.organ.issue_triage_boundary import handle_issue_triage
up = _conduction_values(m)
if a == 'get_issue':
    v['issue'] = {issue!r}
elif a == 'collect_issue_linked_prs':
    v.update(collected=True, merged_prs=[])
elif a == 'collect_issue_covering_prs':
    v.update(collected=True, covering_prs={covering or []!r})
elif a == 'map_repo':
    v['map'] = ''
elif a == 'issue_triage_agent':
    v['stdout'] = {json.dumps({'verdict': verdict, 'reason': reason})!r}
elif a in {{'apply_issue_ready', 'apply_issue_blocked', 'apply_issue_mark', 'apply_issue_manual'}}:
    v['applied'] = False
else:
    v.update(handle_issue_triage(a, {{'config_path': {str(config)!r}}}, up,
                               {{'repo': 'o/r', 'issue_number': 1172, 'live': False}}))
if a == 'summarize_issue_triage':
    Path({str(tmp_path / 'terminal.json')!r}).write_text(json.dumps(v))
""")
    graph = run_graph(tmp_path, script, "semantic-triage", path_id="issue_triage")
    assert graph["effector_results"]["summarize_issue_triage"]["status"] == "succeeded", graph
    return graph, json.loads((tmp_path / "terminal.json").read_text())


@pytest.mark.parametrize("title,body,verdict,reason", [
    ("Document LaunchAgent configuration", "Documentation only; no live operations.", "ready", "documentation_only"),
    ("Document host evidence", "Explain live fleet examples, no live operations.", "ready", "documentation_only"),
    ("Restart LaunchAgent", "Need live host evidence only; no code change.", "skip", "host_ops"),
    ("Restore Hermes and implement detector", "Restore live host; implement src/lokay/intake.py tests.", "split", "host_ops_issue_split"),
])
def test_native_host_prose_reaches_semantic_policy(tmp_path, title, body, verdict, reason):
    graph, terminal = run_triage(tmp_path, title=title, body=body, verdict=verdict, reason=reason)
    assert graph["effector_results"]["issue_triage_agent"]["status"] == "succeeded"
    assert terminal["result"]["decision"]["verdict"] == verdict
    assert terminal["result"]["decision"]["reason"] == reason
    assert terminal["result"]["implementable"] is (verdict == "ready")


@pytest.mark.parametrize("verdict,reason,route", [
    ("skip", "not_oversized; no split required", "skip"),
    ("park", "host_ops_issue_split", "skip"),
    ("skip", "multi_epic is not applicable", "skip"),
    ("split", "independent deliverables", "split"),
    ("ready", "no split required", "do"),
    ("close", "oversized obsolete work", "skip"),
])
def test_native_published_verdict_alone_authorizes_split(tmp_path, verdict, reason, route):
    _, terminal = run_triage(tmp_path / "triage", title="Feature", body="Intentional work",
                             verdict=verdict, reason=reason)
    script = base_effector(f"""from unittest.mock import patch
from lokay.organ.common import _conduction_values
from lokay.organ.issues_boundary import handle_issues
from lokay.organ.issue_triage_department_boundary import handle_issue_triage_department
up = _conduction_values(m)
if a == 'select_next_issue':
    v.update(route='issue', repo='o/r', issue=1172, labels=[])
elif a == 'issues_run_triage':
    with patch('lokay.proc.run_issue_triage_subflow.run_path', return_value={terminal!r}):
        v.update(handle_issues(a, {{}}, up, {{}}))
else:
    def split_child(**kwargs):
        Path({str(tmp_path / 'split.json')!r}).write_text(json.dumps(kwargs))
        return {{'ok': True, 'route': 'completed'}}
    with patch('lokay.proc.run_issue_sieve_split.invoke', side_effect=split_child):
        v.update(handle_issue_triage_department(a, {{}}, up, {{}}))
if a == 'select_issue_sieve':
    Path({str(tmp_path / 'selected.json')!r}).write_text(json.dumps(v))
""")
    graph = run_graph(tmp_path, script, "semantic-sieve", path_id="issue_sieve_row")
    selected = json.loads((tmp_path / "selected.json").read_text())
    assert (selected["repo"], selected["issue"], selected["reason"]) == ("o/r", 1172, reason)
    assert selected["route"] == route
    assert graph["effector_results"]["run_issue_sieve_split"]["status"] == (
        "succeeded" if route == "split" else "skipped")
    assert (tmp_path / "split.json").exists() is (route == "split")
    if route == "split":
        split = json.loads((tmp_path / "split.json").read_text())
        assert (split["repo"], split["issue"]) == ("o/r", 1172)


@pytest.mark.parametrize("state,covering,reason", [
    ("CLOSED", [], "issue_already_closed"),
    ("OPEN", [{"number": 99, "state": "OPEN"}], "duplicate_ai_pr_for_issue"),
])
def test_native_physical_facts_remain_terminal(tmp_path, state, covering, reason):
    graph, terminal = run_triage(tmp_path, title="Document LaunchAgent", body="Docs only",
                                 state=state, covering=covering)
    assert graph["effector_results"]["issue_triage_agent"]["status"] == "skipped"
    assert terminal["result"]["implementable"] is False
    assert terminal["result"]["decision"]["verdict"] == "close"
    assert terminal["result"]["decision"]["reason"] == reason
