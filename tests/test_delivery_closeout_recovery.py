"""Pre-merge producer -> later native department closeout, no open PR dependency."""
import json

import pytest
from test_issue_triage_fala import base_effector, run_graph


def test_merge_effect_has_durable_closeout_intent(tmp_path):
    state = tmp_path / 'state.jsonl'
    config = tmp_path / 'config.yaml'
    config.write_text(f'state:\n  path: {state}\nrepos:\n  - name: o/r\n    clone_path: {tmp_path}\n')
    merged = tmp_path / 'merged'
    body = base_effector(f'''
from lokay.organ.common import _conduction_values
from lokay.organ.lanes import handle_lanes
inputs = {{'config_path': {str(config)!r}, 'live': True, 'repo': 'o/r', 'pr': 57, 'branch': 'ai/fix/42'}}
ctx = {{'cfg': [], 'live': ['--live'], 'repo': 'o/r', 'pr_number': 57, 'issue_number': 42, 'branch': 'ai/fix/42'}}
if a == 'classify_pr_triage_checks': v.update(route='review', head_sha={'b' * 40!r})
elif a == 'resolve_sha_review': v.update(route='cached')
elif a == 'publish_pr_review': v.update(decision={{'verdict':'approve','reviewed_head_sha':{'b' * 40!r}}}, head_sha={'b' * 40!r})
elif a == 'worktree_add': v.update(route='ready')
elif a == 'test_local': v.update(passed=True, tested_head_sha={'b' * 40!r})
elif a == 'select_pr_triage_outcome': v.update(route='merge')
elif a == 'prepare_delivery_closeout': v = handle_lanes(a, inputs, _conduction_values(m), ctx)
elif a == 'pr_merge':
    rows = [json.loads(line) for line in Path({str(state)!r}).read_text().splitlines()] if Path({str(state)!r}).exists() else []
    intents = [row for row in rows if row.get('kind') == 'delivery_closeout_intent']
    assert intents, 'merge effect started without durable closeout intent'
    intent = intents[-1]['intent']
    assert (intent['repo'], intent['pr'], intent['issue'], intent['branch'], intent['head_sha']) == ('o/r', 57, 42, 'ai/fix/42', {'b' * 40!r})
    Path({str(merged)!r}).write_text('merged')
    raise RuntimeError('crash after merge effect before response')
''')
    run_graph(tmp_path, body, 'interrupt-merge', 'pr_triage')
    assert merged.exists(), 'merge did not receive the durable pre-effect intent'


@pytest.mark.parametrize('boundary', ['merge', 'close', 'publish', 'close_failed', 'read_failed', 'edit_failed',
                                      'crash_close', 'crash_edit'])
def test_native_replays_closeout_without_open_prs(tmp_path, boundary):
    test_merge_effect_has_durable_closeout_intent(tmp_path)
    state = tmp_path / 'state.jsonl'
    config = tmp_path / 'config.yaml'
    from test_delivery_receipt import base

    from lokay.delivery_receipt import marker
    provisional = {**base(), 'repo': 'o/r', 'issue': 42, 'branch': 'ai/fix/42',
                   'head_sha': 'b' * 40}
    body_text = marker(provisional)
    if boundary == 'publish':
        from lokay.delivery_receipt import finalize_receipt
        body_text = marker(finalize_receipt(provisional, merge_sha='c' * 40, merged_at='2026-09-21',
                                           issue_closed=True, main_contains_head=True))
    world = tmp_path / 'world.json'
    world.write_text(json.dumps({'closed': boundary in {'close', 'publish'}, 'body': body_text,
                                'closes': 0, 'edits': 0}))
    result_file = tmp_path / 'result.json'
    body = base_effector(f'''
from lokay.organ.common import _conduction_values
from lokay.organ.pr_triage_department_boundary import handle_pr_triage_department
from lokay.proc import list_open_prs
from lokay.config import load_config
from lokay.gh_prs import gh_json
import lokay.gh_prs as gh
import lokay.proc._common as common
world_path = Path({str(world)!r})
def read(carrier, args, **kw):
    w = json.loads(world_path.read_text())
    if {boundary!r} == 'read_failed': raise RuntimeError('read unavailable')
    if args[0] == 'issue': return {{'state': 'CLOSED' if w['closed'] else 'OPEN'}}
    return {{'body': w['body'], 'headRefOid': {'b' * 40!r}, 'headRefName': 'ai/fix/42',
            'headRepository': {{'nameWithOwner': 'o/r'}}, 'baseRefName': 'main',
            'state': 'MERGED', 'mergeCommit': {{'oid': {'c' * 40!r}}}, 'mergedAt': '2026-09-21'}}
def effect(carrier, args, **kw):
    w = json.loads(world_path.read_text())
    if args[0] == 'api': return 'identical'
    if args[:2] == ['issue', 'close']:
        if {boundary!r} == 'close_failed': raise RuntimeError('close unavailable')
        w['closed'] = True; w['closes'] += 1
    elif args[:2] == ['pr', 'edit']:
        if {boundary!r} == 'edit_failed': raise RuntimeError('edit unavailable')
        w['body'] = args[args.index('--body') + 1]; w['edits'] += 1
    else: raise AssertionError(args)
    world_path.write_text(json.dumps(w))
    if ({boundary!r} == 'crash_close' and args[0] == 'issue') or ({boundary!r} == 'crash_edit' and args[0] == 'pr'):
        raise RuntimeError('crash after applied effect before response')
    return ''
gh.gh_json = read; gh.gh_text = effect
common.mutations_allowed = lambda **kw: True
list_open_prs._list_open = lambda *args, **kw: {{'ok': True, 'prs': []}}
if a == 'run_pr_sieve': raise AssertionError('recovery cannot review or merge again')
v = handle_pr_triage_department(a, {{'config_path': {str(config)!r}, 'live': True,
    'incomplete_retry_position': 'tail'}}, _conduction_values(m), {{}})
if a == 'summarize_pr_triage_department': Path({str(result_file)!r}).write_text(json.dumps(v))
''')
    replay = tmp_path / 'replay'
    replay.mkdir()
    result = run_graph(replay, body, 'replay', 'pr_triage_department')
    assert result['ok'] is True, result
    summary = json.loads(result_file.read_text())
    confirmed = boundary not in {'close_failed', 'read_failed', 'edit_failed', 'crash_close', 'crash_edit'}
    assert summary['triage']['delivery_confirmed'] is confirmed
    assert summary['repo'] == 'o/r' and summary['pr'] == 57
    if confirmed:
        assert summary['triage']['issue_closed'] is True
        assert summary['triage']['closed_issue'] == 42
    else:
        assert summary['triage']['reason'].startswith('delivery_')
        assert summary['leftover_prs'][-1]['pr'] == 57
        if boundary in {'edit_failed', 'crash_edit'}:
            assert summary['triage']['issue_closed'] is True
            assert summary['triage']['closed_issue'] == 42
    from lokay.proc.delivery_closeout import pending
    assert bool(pending(state)) is (not confirmed)
    observed = json.loads(world.read_text())
    assert observed['closes'] == int(boundary in {'merge', 'edit_failed', 'crash_close', 'crash_edit'})
    assert observed['edits'] == int(boundary in {'merge', 'close', 'crash_edit'})
    if boundary in {'crash_close', 'crash_edit'}:
        retry = tmp_path / 'retry'
        retry.mkdir()
        result = run_graph(retry, body, 'retry', 'pr_triage_department')
        assert result['ok'] is True
        assert json.loads(result_file.read_text())['triage']['delivery_confirmed'] is True
        assert pending(state) == []
        assert json.loads(world.read_text())['closes'] == 1
        assert json.loads(world.read_text())['edits'] == 1


def test_failed_intent_is_named_pending_in_child_summary():
    from lokay.organ.pr_outcome import handle_pr_outcome
    result = handle_pr_outcome('summarize_pr_triage', {}, {
        'publish_pr_review': {'decision': {'verdict': 'approve'}},
        'select_pr_triage_outcome': {'route': 'merge'},
        'prepare_delivery_closeout': {'ok':True, 'route':'pending', 'reason':'delivery_closeout_intent_failed'},
        'pr_merge': {'skipped':True, 'reason':'condition_not_met'}}, {})
    assert result is not None
    assert result['result']['reason'] == 'delivery_closeout_intent_failed'
    assert result['result']['waiting'] is True


def test_ledger_compaction_preserves_pending_closeout(tmp_path):
    test_merge_effect_has_durable_closeout_intent(tmp_path)
    from lokay.proc.delivery_closeout import pending
    from lokay.state_compact import compact_state
    state = tmp_path / 'state.jsonl'
    before = pending(state)
    assert len(before) == 1
    compact_state(state, min_bytes=0)
    assert pending(state) == before


def test_pending_replay_is_not_suppressed_or_allowed_to_starve_other_prs():
    from lokay.proc.select_next_pr import select
    from lokay.proc.summarize_pr_triage_department import summarize
    replay = {'repo': 'o/r', 'pr': 57, 'branch': 'ai/fix/42', 'head_sha': 'b' * 40,
              'delivery_replay': True}
    other = {'repo': 'o/other', 'pr': 2, 'branch': 'ai/fix/2', 'head_sha': 'c' * 40}
    last = {'skipped_pr_repo': 'o/r', 'skipped_pr': 57, 'skipped_head_sha': 'b' * 40}
    picked = select({'prs': [replay, other]}, last)
    assert picked['pr'] == 57
    summary = summarize(picked, {'triage': {'merged': True, 'delivery_confirmed': False}},
                        {'verdict': 'merge'}, {'route': 'review'}, incomplete_retry_position='tail')
    assert summary['leftover_prs'][0] == other
    assert select({'prs': [replay, other]}, summary)['repo'] == 'o/other'


def test_closeout_preserves_keep_issue_open(tmp_path, monkeypatch):
    from lokay.organ.lanes import handle_lanes
    from lokay.proc.delivery_closeout import close, pending
    config = tmp_path / 'config.yaml'
    config.write_text(f'state:\n  path: {tmp_path / "state.jsonl"}\n')
    out = handle_lanes('prepare_delivery_closeout', {'config_path':str(config), 'live':True, 'keep_issue_open':True},
        {'publish_pr_review':{'decision':{'verdict':'approve', 'reviewed_head_sha':'b' * 40}},
         'test_local':{'ok':True,'tested_head_sha':'b' * 40}},
        {'cfg':[], 'live':['--live'], 'repo':'o/r', 'pr_number':57, 'issue_number':42, 'branch':'ai/fix/42'})
    assert out is not None
    assert out['route'] == 'ready'
    intent = pending(tmp_path / 'state.jsonl')[0]
    monkeypatch.setattr('lokay.gh_prs.gh_json', lambda *a, **kw: pytest.fail('protected closeout read'))
    out = close(picked={**intent, 'delivery_replay':True, 'closeout_intent':intent}, config_path=str(config), live=True)
    assert out['reason'] == 'delivery_keep_issue_open'


def test_pre_merge_interruption_reenters_review_not_replay_merge(tmp_path, monkeypatch):
    test_merge_effect_has_durable_closeout_intent(tmp_path)
    from lokay.proc.delivery_closeout import observe, pending
    intent = pending(tmp_path / 'state.jsonl')[0]
    monkeypatch.setattr('lokay.gh_prs.gh_json', lambda *a, **kw: {
        'state':'OPEN', 'headRefOid':'b' * 40, 'headRefName':'ai/fix/42',
        'headRepository':{'nameWithOwner':'o/r'}, 'baseRefName':'main'})
    monkeypatch.setattr('lokay.gh_prs.gh_text', lambda *a, **kw: pytest.fail('OPEN replay effect'))
    picked = {**intent, 'delivery_replay':True, 'closeout_intent':intent}
    assert observe(picked=picked, config_path=str(tmp_path / 'config.yaml'), live=True)['route'] == 'review'
    monkeypatch.setattr('lokay.gh_prs.gh_json', lambda *a, **kw: pytest.fail('dry-run read'))
    assert observe(picked=picked, config_path=str(tmp_path / 'config.yaml'), live=False)['route'] == 'pending'


def test_listing_failure_and_bad_unrelated_event_do_not_hide_intent(tmp_path, monkeypatch):
    test_merge_effect_has_durable_closeout_intent(tmp_path)
    from lokay.proc import list_open_prs
    from lokay.state import append_event
    state = tmp_path / 'state.jsonl'
    append_event(state, {'kind':'delivery_closeout_intent', 'intent':{'repo':'bad/repo'}})
    monkeypatch.setattr(list_open_prs, '_list_open', lambda *a, **kw: {'ok':False, 'error':'offline'})
    listed = list_open_prs.run(config_path=str(tmp_path / 'config.yaml'), live=True)
    assert listed['ok'] is True
    assert [(row['repo'],row['pr']) for row in listed['prs']] == [('o/r',57)]


def test_receipt_final_read_cannot_drift_from_replay_intent(tmp_path, monkeypatch):
    test_merge_effect_has_durable_closeout_intent(tmp_path)
    from test_delivery_receipt import base

    from lokay.delivery_receipt import marker
    from lokay.proc.delivery_closeout import pending, publish
    intent = pending(tmp_path / 'state.jsonl')[0]
    reads = []
    def read(carrier, args, **kw):
        if args[0] == 'issue': return {'state':'CLOSED'}
        reads.append(args)
        head = 'b' * 40 if len(reads) == 1 else 'c' * 40
        return {'headRefOid':head, 'headRefName':'ai/fix/42', 'headRepository':{'nameWithOwner':'o/r'},
                'baseRefName':'main', 'state':'MERGED', 'mergeCommit':{'oid':'d' * 40}, 'mergedAt':'time',
                'body':marker({**base(), 'repo':'o/r', 'issue':42, 'head_sha':head})}
    monkeypatch.setattr('lokay.gh_prs.gh_json', read)
    edits = []
    monkeypatch.setattr('lokay.gh_prs.gh_text', lambda carrier,args,**kw: 'identical' if args[0]=='api' else edits.append(args))
    monkeypatch.setattr('lokay.proc._common.mutations_allowed', lambda **kw: True)
    result = publish(picked={**intent, 'delivery_replay':True, 'closeout_intent':intent},
                     config_path=str(tmp_path / 'config.yaml'), live=True)
    assert result.get('confirmed') is not True
    assert edits == []


def test_live_merge_atom_refuses_missing_durable_intent(tmp_path, monkeypatch):
    from lokay.config import Config
    from lokay.organ.lanes import handle_lanes
    monkeypatch.setattr('lokay.config.load_config', lambda _: Config(merge_enabled=True))
    monkeypatch.setattr('lokay.merge_policy.decide_auto_merge', lambda **kw: type('Gate', (), {'action': 'merge'})())
    out = handle_lanes('pr_merge', {'live': True}, {
        'publish_pr_review': {'decision': {'verdict': 'approve', 'reviewed_head_sha': 'b' * 40}},
        'test_local': {'ok': True, 'passed': True, 'tested_head_sha': 'b' * 40}},
        {'cfg': [], 'live': ['--live'], 'repo': 'o/r', 'pr_number': 57, 'issue_number':42,
         'branch':'ai/fix/42', 'run_atom_main': lambda *a: {'ok': True, 'merged': True}})
    assert out is not None
    assert out['reason'] == 'delivery_closeout_intent_missing'
    assert out.get('merged') is not True


@pytest.mark.parametrize('field,value', [('headRefOid', 'c' * 40), ('headRefName', 'ai/fix/99'),
                                        ('headRepository', {'nameWithOwner': 'foreign/repo'}),
                                        ('baseRefName', 'develop'), ('state', 'CLOSED')])
def test_replay_refuses_changed_remote_identity(tmp_path, monkeypatch, field, value):
    test_merge_effect_has_durable_closeout_intent(tmp_path)
    from lokay.proc.delivery_closeout import close, pending
    intent = pending(tmp_path / 'state.jsonl')[0]
    remote = {'headRefOid': 'b' * 40, 'headRefName': 'ai/fix/42', 'headRepository': {'nameWithOwner':'o/r'},
              'baseRefName':'main', 'state':'MERGED', 'mergedAt':'time', 'mergeCommit':{'oid':'c' * 40}}
    monkeypatch.setattr('lokay.gh_prs.gh_json', lambda *a, **kw: {**remote, field: value})
    monkeypatch.setattr('lokay.gh_prs.gh_text', lambda *a, **kw: pytest.fail('identity drift reached effect'))
    result = close(picked={**intent, 'delivery_replay':True, 'closeout_intent':intent},
                   config_path=str(tmp_path / 'config.yaml'), live=True)
    assert result['route'] == 'pending'
    assert result['reason'] in {'delivery_closeout_identity_mismatch', 'delivery_merge_unconfirmed'}
