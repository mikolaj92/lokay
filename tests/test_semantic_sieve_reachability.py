"""Production sieve must reach semantic triage without admitting raw inbox to coding."""

import json
from types import SimpleNamespace

import pytest
from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector
from test_typed_decisions import config, endpoint  # noqa: F401 — pytest fixture


def test_native_inbox_sieve_reaches_triage_but_executor_stays_ready_only(tmp_path):
    from lokay.proc.select_next_issue import select

    listed = {'issues': [{'repo': 'o/r', 'issue': 7, 'labels': ['bug'],
                          'assignees': [], 'title': 'One implementable fix'}]}
    assert select(listed, occupied=set())['route'] == 'none'
    script = base_effector(f"""from lokay.organ.common import _conduction_values
from lokay.organ.issues_boundary import handle_issues
from lokay.organ.issue_triage_department_boundary import handle_issue_triage_department
up = _conduction_values(m)
if a in {{'select_next_issue', 'select_issue_sieve_candidate'}}:
    v.update(handle_issues(a, {{'listed': {listed!r}, 'last': {{}}, 'live': False}}, up, {{}}))
elif a == 'issues_run_triage':
    Path({str(tmp_path / 'triage-called.json')!r}).write_text(json.dumps(up['select_next_issue']))
    v.update(route='completed', triage={{'result': {{'decision': {{'verdict': 'ready', 'reason': 'decision_ready'}}}}}})
else:
    v.update(handle_issue_triage_department(a, {{'listed': {listed!r}}}, up, {{}}))
if a == 'summarize_issue_sieve_row':
    Path({str(tmp_path / 'terminal.json')!r}).write_text(json.dumps(v))
""")
    graph = run_graph(tmp_path, script, 'inbox-to-semantic', path_id='issue_sieve_row')
    assert graph['effector_results']['issues_run_triage']['status'] == 'succeeded'
    selected = json.loads((tmp_path / 'triage-called.json').read_text())
    assert (selected['repo'], selected['issue'], selected['route']) == ('o/r', 7, 'issue')
    terminal = json.loads((tmp_path / 'terminal.json').read_text())['result']
    assert terminal['route'] == 'do'
    assert terminal['launched'] is None


def test_sieve_does_not_inherit_executor_ready_only_leftover(tmp_path):
    from lokay.proc.prepare_issue_sieve import prepare
    from lokay.proc.select_issue_sieve_candidate import select

    listed = {'issues': [{'repo': 'o/r', 'issue': n, 'labels': []} for n in (1, 2)]}
    prepared = prepare(listed=listed, last={'leftover_issues': []},
                       pass_dir=str(tmp_path), config_path=None, live=True,
                       budget=2, slot_count=5)
    assert select(listed, prepared['last'], occupied=set())['issue'] == 1


def test_sieve_tail_rotates_across_passes_and_preserves_resume_budget(tmp_path):
    from lokay.proc.classify_issue_sieve_row import classify
    from lokay.proc.prepare_issue_sieve import prepare
    from lokay.proc.select_issue_sieve_candidate import select

    cfg = tmp_path / 'config.yaml'
    cfg.write_text(f'repos: []\nstate:\n  path: {tmp_path / "state.jsonl"}\n')
    listed = {'issues': [{'repo': 'o/r', 'issue': n, 'labels': []} for n in (1, 2, 3)]}
    kwargs = dict(listed=listed, last={}, config_path=str(cfg), live=True,
                  budget=1, slot_count=5)
    first = prepare(pass_dir=str(tmp_path / 'pass-1'), **kwargs)
    chosen = select(listed, first['last'], occupied=set())
    assert chosen['issue'] == 1
    result = classify({'route': 'run', 'slot': 1}, {'result': {
        **chosen, 'route': 'skip', 'reason': 'decision_uncertain',
        'leftover': 2, 'leftover_issues': listed['issues'][1:]}}, prepared=first)
    assert result['route'] == 'cap'
    resumed = prepare(pass_dir=str(tmp_path / 'pass-1'), **kwargs)
    assert resumed['budget'] == 0
    assert resumed['spent'] == 1
    second = prepare(pass_dir=str(tmp_path / 'pass-2'), **kwargs)
    assert select(listed, second['last'], occupied=set())['issue'] == 2


def test_sieve_respects_operator_readiness_ownership_occupancy_and_tracker():
    from lokay.proc.select_issue_sieve_candidate import select

    listed = {'issues': [
        {'repo': 'o/r', 'issue': 1, 'labels': ['ready-for-agent']},
        {'repo': 'o/r', 'issue': 2, 'labels': [], 'assignees': ['foreign']},
        {'repo': 'o/busy', 'issue': 3, 'labels': []},
        {'repo': 'o/r', 'issue': 4, 'labels': ['ai:tracker']},
        {'repo': 'o/r', 'issue': 5, 'labels': ['ai:ready']},
        {'repo': 'o/r', 'issue': 6, 'labels': []},
    ]}
    out = select(listed, occupied={'o/busy'})
    assert (out['issue'], out['route']) == (6, 'issue')
    assert out['leftover_issues'] == []


def test_stale_tail_cannot_hide_new_undecided_work(tmp_path):
    from lokay.proc.prepare_issue_sieve import prepare
    from lokay.proc.select_issue_sieve_candidate import select

    cfg = tmp_path / 'config.yaml'
    cfg.write_text(f'repos: []\nstate:\n  path: {tmp_path / "state.jsonl"}\n')
    (tmp_path / 'issue-sieve-tail.json').write_text(json.dumps({
        'department': 'issue_triage',
        'leftover_issues': [{'repo': 'o/r', 'issue': 1, 'labels': []}]}))
    listed = {'issues': [{'repo': 'o/r', 'issue': 2, 'labels': []}]}
    prepared = prepare(listed=listed, last={}, pass_dir=str(tmp_path / 'pass'),
                       config_path=str(cfg), live=True, budget=1, slot_count=5)
    assert select(listed, prepared['last'], occupied=set())['issue'] == 2


def test_malformed_durable_tail_does_not_crash_or_admit_missing_work(tmp_path):
    from lokay.proc.prepare_issue_sieve import prepare
    from lokay.proc.select_issue_sieve_candidate import select

    cfg = tmp_path / 'config.yaml'
    cfg.write_text(f'repos: []\nstate:\n  path: {tmp_path / "state.jsonl"}\n')
    (tmp_path / 'issue-sieve-tail.json').write_text(json.dumps({
        'leftover_issues': ['not-a-row', {'repo': 'o/r', 'issue': 'invalid'}]}))
    listed = {'issues': [{'repo': 'o/r', 'issue': 2, 'labels': []}]}
    prepared = prepare(listed=listed, last={}, pass_dir=str(tmp_path / 'pass'),
                       config_path=str(cfg), live=True, budget=1, slot_count=5)
    assert select(listed, prepared['last'], occupied=set())['issue'] == 2


@pytest.mark.parametrize('choice,route', [('ready', 'do'), ('skip', 'skip')])
def test_executor_admission_uses_one_configured_queue_decision(tmp_path, endpoint, monkeypatch, choice, route):  # noqa: F811 — endpoint is a pytest fixture
    from lokay.config import RepoConfig
    from lokay.organ.issues_boundary import handle_issues
    from lokay.proc.semantic_decision import QUEUE_OPTIONS
    from lokay.tasks import MemoryTasks

    url, calls, response = endpoint
    cfg = config(tmp_path, url)
    cfg.repos = [RepoConfig(name='o/r', clone_path=tmp_path)]
    cfg.decision_routes = {'queue_conflict': 'local'}
    response['answers'] = {'queue_conflict': {'type': 'choice', 'choice': choice,
        'probabilities': {k: .97 if k == choice else .01 for k in QUEUE_OPTIONS}}}
    source = MemoryTasks(target='o/r')
    source.seed(2, title='One fix', body='Implement one coherent fix', labels=['ai:ready'])
    source.seed(3, title='Another fix', body='Independent peer', labels=['ai:ready'])
    monkeypatch.setattr('lokay.config.load_config', lambda *_: cfg)
    monkeypatch.setattr('lokay.config.department_enabled', lambda *_: True)
    monkeypatch.setattr('lokay.proc.inspect_repo_pr_admission.inspect',
                        lambda **_: {'allowed': True, 'reason': 'pr_first_clear'})
    monkeypatch.setattr('lokay.proc.check_executor_queue.load_tasks', lambda *a, **kw: source)
    monkeypatch.setattr('lokay.proc.check_executor_queue.load_code', lambda *a, **kw:
                        SimpleNamespace(pr=SimpleNamespace(list_open=list)))
    out = handle_issues('select_issue_executor', {'config_path': str(cfg.config_path), 'live': True}, {
        'select_issue_do_row': {'route': 'do', 'repo': 'o/r', 'issue': 2,
                               'leftover': 2, 'leftover_issues': [
                                   {'repo': 'o/r', 'issue': 2, 'labels': ['ai:ready']},
                                   {'repo': 'o/r', 'issue': 3, 'labels': ['ai:ready']}]}}, {})
    assert out['route'] == route
    assert len(calls) == 1
    assert list(calls[0][1]['questions']) == ['queue_conflict']
    evidence = json.loads(calls[0][1]['state'])
    assert evidence['candidate']['body'] == 'Implement one coherent fix'
    assert [row['number'] for row in evidence['peer_issues']] == [3]
    assert (out['queue_decision']['repo'], out['queue_decision']['issue']) == ('o/r', 2)
    if route == 'skip':
        assert out['reason'] == 'decision_skip'
        assert [row['issue'] for row in out['leftover_issues']] == [3]


def test_three_sieve_slots_spend_exactly_three_without_reset(tmp_path):
    from lokay.organ.issue_triage_department_boundary import (
        handle_issue_triage_department,
    )
    from lokay.proc.prepare_issue_sieve import prepare

    prepared = prepare(listed={'issues': [{'repo': 'o/r', 'issue': n} for n in range(1, 5)]},
                       last={}, pass_dir=str(tmp_path), config_path=None,
                       live=True, budget=3, slot_count=5)
    up = {'prepare_issue_sieve': prepared}
    for slot in range(1, 4):
        selected = handle_issue_triage_department(f'select_issue_sieve_slot_{slot}', {}, up, {})
        assert selected['route'] == 'run'
        up[f'select_issue_sieve_slot_{slot}'] = selected
        up[f'run_issue_sieve_row_{slot}'] = {'result': {
            'repo': 'o/r', 'issue': slot, 'route': 'skip', 'reason': 'decision_uncertain',
            'leftover': 4 - slot, 'leftover_issues': [{'repo': 'o/r', 'issue': n} for n in range(slot + 1, 5)]}}
        classified = handle_issue_triage_department(f'classify_issue_sieve_row_{slot}', {}, up, {})
        up[f'classify_issue_sieve_row_{slot}'] = classified
        assert classified['spent'] == slot
    assert classified['route'] == 'cap'
    assert handle_issue_triage_department('select_issue_sieve_slot_4', {}, up, {})['route'] == 'empty'
    resumed = prepare(listed=prepared['listed'], last={}, pass_dir=str(tmp_path),
                       config_path=None, live=True, budget=3, slot_count=5)
    assert resumed['spent'] == 3 and resumed['budget'] == 0


def test_queue_evidence_failure_skips_without_http_or_consuming_next_candidate(tmp_path, endpoint, monkeypatch):  # noqa: F811 — endpoint is a pytest fixture
    from lokay.config import RepoConfig
    from lokay.proc.check_executor_queue import check

    url, calls, _ = endpoint
    cfg = config(tmp_path, url)
    cfg.repos = [RepoConfig(name='o/r', clone_path=tmp_path)]
    cfg.decision_routes = {'queue_conflict': 'local'}
    def unavailable(*args, **kwargs):
        raise RuntimeError('source unavailable')
    monkeypatch.setattr('lokay.proc.check_executor_queue.load_tasks', unavailable)
    selected = {'route': 'do', 'repo': 'o/r', 'issue': 1}
    listed = {'issues': [{'repo': 'o/r', 'issue': n} for n in (1, 2)]}
    out = check(cfg=cfg, selected=selected, listed=listed, runner=object(), live=True)
    assert out['route'] == 'skip' and out['reason'] == 'queue_evidence_unavailable'
    assert [row['issue'] for row in out['leftover_issues']] == [2]
    assert calls == []
