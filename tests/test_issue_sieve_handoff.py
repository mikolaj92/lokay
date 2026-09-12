"""Issue-bound sieve decisions survive the department boundary (#1105)."""

from lokay.proc.select_issue_sieve_result import select as reduce_sieve
from lokay.proc.select_issue_do_row import select as select_do
from lokay.proc.select_next_issue import select as pick


def decision(issue, route, reason):
    return {"repo": "o/r", "issue": issue, "route": route, "reason": reason}


def test_sieve_receipt_keeps_all_decisions_not_just_last():
    rows = [
        {"route": "continue", "result": decision(1, "skip", "host_ops")},
        {"route": "cap", "result": decision(2, "do", "ready")},
        {"route": "empty"},
    ]
    result = reduce_sieve({"cap": 2}, rows)["result"]
    assert result["decisions"] == [decision(1, "skip", "host_ops"), decision(2, "do", "ready")]


def test_executor_uses_bound_decision_without_ready_label():
    rows = [{"repo": "o/r", "issue": n, "labels": []} for n in (1, 2)]
    rows[0]["sieve_decision"] = decision(1, "skip", "host_ops")
    rows[1]["sieve_decision"] = decision(2, "do", "ready")
    listed = {"ok": True, "issues": rows}
    skipped = select_do({**rows[0], "route": "issue"}, listed)
    assert skipped["route"] == "skip"
    assert skipped["reason"] == "host_ops"
    assert [r["issue"] for r in skipped["leftover_issues"]] == [2]
    selected = pick(listed, skipped, occupied=set())
    assert selected["issue"] == 2
    assert select_do(selected, listed)["route"] == "do"


def test_foreign_decision_does_not_authorize_issue():
    picked = {"repo": "o/r", "issue": 2, "labels": [], "route": "issue",
              "sieve_decision": decision(1, "do", "ready")}
    assert select_do(picked)["route"] == "skip"


def test_explicit_skip_wins_over_stale_ready_label():
    picked = {"repo": "o/r", "issue": 1, "labels": ["ai:ready"], "route": "ready",
              "sieve_decision": decision(1, "skip", "host_ops")}
    assert select_do(picked)["route"] == "skip"


def test_executor_rows_attach_decisions_to_fresh_issue_list(monkeypatch):
    from lokay.proc.run_executor_rows import run
    captured = {}
    def capture(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "result": {}}
    monkeypatch.setattr("lokay.proc.run_executor_rows.run_path", capture)
    fresh = {"ok": True, "issues": [{"repo": "o/r", "issue": 2, "labels": []}]}
    run(listed=fresh, config_path=None, live=False, pass_dir="", budget=1,
        triage={"decisions": [decision(1, "do", "ready"), decision(2, "do", "ready")]})
    rows = captured["extra_inputs"]["listed"]["issues"]
    assert len(rows) == 1  # Closed/absent issues must never be resurrected.
    assert rows[0]["sieve_decision"] == decision(2, "do", "ready")
    assert "sieve_decision" not in fresh["issues"][0]


def test_authored_parent_conducts_completed_sieve_to_executor(monkeypatch):
    import tomllib
    from pathlib import Path
    from lokay.organ.departments_boundary import handle_departments
    package = tomllib.loads((Path(__file__).parents[1] / 'fala/lokay.fala-package.toml').read_text())
    path = next(p for p in package['correlation_paths'] if p['id'] == 'factory_pass')
    nodes = {e['id']: e for e in path['effectors']}
    assert 'run_issue_triage_department' in nodes['select_executor_department']['conduction']
    outputs = {'factory_begin': {'pass_dir': '/pass'},
               'select_executor_department': {'route': 'run'},
               'select_issue_triage_department': {'route': 'run'},
               'run_issue_triage_department': {'result': {'decisions': [decision(2, 'do', 'ready')]}}}
    up = {k: outputs[k] for k in nodes['run_executor_department']['conduction']}
    captured = {}
    def capture(**kwargs):
        captured.update(kwargs)
        return {'ok': True}
    monkeypatch.setattr('lokay.proc.run_executor_department.run', capture)
    handle_departments('run_executor_department', {'live': False}, up, {})
    assert captured['pass_dir'] == '/pass'
    assert captured['triage'] == outputs['run_issue_triage_department']['result']


def test_authored_parent_conducts_fala_flat_sieve_to_executor(monkeypatch):
    import tomllib
    from pathlib import Path
    from lokay.organ.departments_boundary import handle_departments
    package = tomllib.loads((Path(__file__).parents[1] / 'fala/lokay.fala-package.toml').read_text())
    path = next(p for p in package['correlation_paths'] if p['id'] == 'factory_pass')
    nodes = {e['id']: e for e in path['effectors']}
    flat = {
        'ok': True,
        'department': 'issue_triage',
        'decisions': [decision(42, 'skip', 'host_ops')],
        'leftover': 108,
        'leftover_issues': [{'repo': 'o/r', 'issue': 53}],
    }
    outputs = {'factory_begin': {'pass_dir': '/pass'},
               'select_executor_department': {'route': 'run'},
               'select_issue_triage_department': {'route': 'run'},
               'run_issue_triage_department': flat}
    up = {k: outputs[k] for k in nodes['run_executor_department']['conduction']}
    captured = {}
    def capture(**kwargs):
        captured.update(kwargs)
        return {'ok': True}
    monkeypatch.setattr('lokay.proc.run_executor_department.run', capture)
    handle_departments('run_executor_department', {'live': False}, up, {})
    assert captured['triage']['decisions'] == [decision(42, 'skip', 'host_ops')]
    assert captured['triage']['leftover_issues'][0]['issue'] == 53


def test_sieve_resume_retains_decisions_from_earlier_slots(tmp_path):
    from lokay.proc.classify_issue_sieve_row import classify
    from lokay.proc.prepare_issue_sieve import prepare
    listed = {'ok': True, 'issues': [{'repo': 'o/r', 'issue': n} for n in (1, 2, 3)]}
    initial = prepare(listed=listed, last={}, pass_dir=str(tmp_path), config_path=None,
                      live=False, budget=5, slot_count=5)
    first = classify({'route': 'run', 'slot': 1},
                     {'result': {**decision(1, 'do', 'ready'), 'leftover': 2,
                                 'leftover_issues': listed['issues'][1:]}}, prepared=initial)
    resumed = prepare(listed=listed, last={}, pass_dir=str(tmp_path), config_path=None,
                      live=False, budget=5, slot_count=5)
    assert resumed['decisions'] == [decision(1, 'do', 'ready')]
    second = classify({'route': 'run', 'slot': 1},
                      {'result': {**decision(2, 'skip', 'host_ops'), 'leftover': 1,
                                  'leftover_issues': listed['issues'][2:]}}, prepared=resumed)
    result = reduce_sieve(resumed, [second])['result']
    assert result['decisions'] == [decision(1, 'do', 'ready'), decision(2, 'skip', 'host_ops')]
    again = prepare(listed=listed, last={}, pass_dir=str(tmp_path), config_path=None,
                    live=False, budget=5, slot_count=5)
    assert again['decisions'] == result['decisions']


def test_serial_sieve_cursor_keeps_all_previous_decisions(tmp_path):
    from lokay.proc.classify_issue_sieve_row import classify
    from lokay.proc.prepare_issue_sieve import read_cursor
    prepared = {'cap': 5, 'spent': 0, 'pass_dir': str(tmp_path)}
    first = classify({'route': 'run', 'slot': 1},
                     {'result': {**decision(1, 'do', 'ready'), 'leftover': 2}}, prepared=prepared)
    classify({'route': 'run', 'slot': 2},
             {'result': {**decision(2, 'skip', 'host_ops'), 'leftover': 1}},
             prepared=prepared, previous=first)
    assert read_cursor(str(tmp_path))['decisions'] == [decision(1, 'do', 'ready'), decision(2, 'skip', 'host_ops')]


def test_triage_failure_is_not_a_completed_skip_decision():
    rows = [{'route': 'cap', 'result': decision(1, 'skip', 'adapter_failed')}]
    assert reduce_sieve({'cap': 1}, rows)['result']['decisions'] == []


def test_invalid_decision_route_type_does_not_crash():
    from lokay.sieve_decision import decision_of
    assert decision_of({'repo': 'o/r', 'issue': 1, 'route': []}) is None
