"""C5: actual child summary -> wrapper -> native department -> disk receipt."""
import json
from pathlib import Path

import pytest
from test_issue_triage_fala import base_effector, run_graph


@pytest.mark.parametrize('confirmed', [False, True])
def test_delivery_evidence_survives_native_department_to_disk(tmp_path, confirmed):
    from lokay.proc.summarize_pr_triage import summarize

    receipt = {'receipt_digest': 'sha256:' + 'd' * 64, 'head_sha': 'b' * 40,
               'issue_closed': True} if confirmed else {}
    child = summarize(review={'decision': {'verdict': 'approve'}}, repair={},
                      repair_manual={}, manual={}, merge={'merged': True},
                      close={'ok': confirmed, 'closed': confirmed, 'issue': 42},
                      receipt={'confirmed': confirmed, 'issue_closed': confirmed,
                               'receipt': receipt, 'reason': 'close_failed'})
    config = tmp_path / 'config.yaml'
    config.write_text(f'state:\n  path: {tmp_path / "state.jsonl"}\n')
    result_path = tmp_path / 'department.json'
    body = base_effector(f'''
from lokay.organ.common import _conduction_values
from lokay.organ.pr_triage_department_boundary import handle_pr_triage_department
from lokay.proc import run_pr_triage_subflow
run_pr_triage_subflow.run_path = lambda **kw: {{'ok': True, 'terminal': {{'summarize_pr_triage': {child!r}}}}}
if a == 'list_pr_sieve': v.update(prs=[{{'repo':'o/r','pr':57,'branch':'ai/fix/42','head_sha':{'b' * 40!r}}}])
elif a == 'reconcile_pr_repair_push': v.update(route='review', recovery_case='none', repo='o/r', pr=57, branch='ai/fix/42')
else:
    v = handle_pr_triage_department(a, {{'config_path': {str(config)!r}, 'live': True}}, _conduction_values(m), {{}})
if a == 'summarize_pr_triage_department': Path({str(result_path)!r}).write_text(json.dumps(v))
''')
    result = run_graph(tmp_path, body, 'delivery-completion', 'pr_triage_department')
    assert result['ok'] is True, result
    department = json.loads(result_path.read_text())
    from lokay.proc.record_pass import record
    recorded = record(begin={'state_path': str(tmp_path / 'state.jsonl'), 'live': True}, prs=department)
    disk = json.loads(Path(recorded['result']['pass_receipt_path']).read_text())
    assert disk['outcome'] == 'merge'  # The merge remains a genuine separate fact.
    assert disk['pr_triage'].get('delivery_confirmed') is confirmed
    assert disk['pr_triage']['issue_closed'] is confirmed
    assert disk['pr_triage']['closed_issue'] == (42 if confirmed else 0)
    assert disk['pr_triage']['delivery_receipt'] == receipt
    assert disk['delivery_confirmed'] is confirmed
    assert disk['merged_count'] == 1
    assert disk['delivered_count'] == int(confirmed)
    if not confirmed:
        assert disk['pr_triage']['reason'] == 'close_failed'


def test_failed_close_does_not_claim_closed_issue():
    from lokay.proc.summarize_pr_triage import summarize
    result = summarize(review={'decision': {'verdict': 'approve'}}, repair={},
                       repair_manual={}, manual={}, merge={'merged': True},
                       close={'ok': False, 'issue': 42})['result']
    assert result['merged'] is True
    assert result.get('issue_closed') is False
    assert result['closed_issue'] == 0


def test_dry_run_receipt_never_reads_or_creates_repair_state(monkeypatch):
    from lokay.organ.lanes import handle_lanes
    monkeypatch.setattr('lokay.proc.pr_repair_receipts.read', lambda *a, **kw: pytest.fail('dry-run read state'))
    out = handle_lanes('publish_delivery_receipt', {'live':False}, {},
        {'cfg':[], 'live':[], 'repo':'o/r', 'pr_number':57, 'issue_number':42, 'branch':'ai/fix/42'})
    assert out is not None
    assert out['route'] == 'planned'
    assert out['confirmed'] is False


def test_receipt_edit_requires_mutation_authority(monkeypatch):
    from test_delivery_receipt import base

    from lokay.config import Config
    from lokay.delivery_receipt import marker
    from lokay.organ.lanes import handle_lanes
    monkeypatch.setattr('lokay.config.load_config', lambda _: Config())
    monkeypatch.setattr('lokay.proc._common.mutations_allowed', lambda **kw: False)
    monkeypatch.setattr('lokay.proc.pr_repair_receipts.read', lambda *a, **kw: {})
    monkeypatch.setattr('lokay.gh_prs.gh_json', lambda *a, **kw: {'body':marker(base()), 'headRefOid':'b' * 40,
                         'mergeCommit':{'oid':'m'}, 'mergedAt':'t', 'state':'CLOSED'})
    def text(carrier, args, **kw):
        if args[0] == 'api': return 'identical'
        pytest.fail('unauthorized receipt edit')
    monkeypatch.setattr('lokay.gh_prs.gh_text', text)
    out = handle_lanes('publish_delivery_receipt', {'live':True}, {'pr_merge':{'merged':True}},
        {'cfg':[], 'live':['--live'], 'repo':'a/b', 'pr_number':9, 'issue_number':7, 'branch':'ai/fix/7'})
    assert out is not None
    assert out['confirmed'] is False


def test_pass_receipt_does_not_copy_transport_inside_delivery_receipt():
    from lokay.proc.record_pass import _typed_pr_fields
    out = _typed_pr_fields({'delivery_receipt': {'head_sha':'b'*40, 'terminal':{'stdout':'private'},
                                                 'run_refs':[{'run_id':'r', 'stdout':'secret'}]}})
    assert out['delivery_receipt'] == {'head_sha':'b'*40, 'run_refs':[{'run_id':'r'}]}


def test_planned_merge_is_not_counted_as_real_merge():
    from lokay.proc.summarize_pr_triage import summarize
    result = summarize(review={'decision': {'verdict': 'approve'}}, repair={},
                       repair_manual={}, manual={}, merge={'planned': True},
                       close={'planned': True, 'issue': 42})['result']
    assert result['merged'] is False
    assert result.get('planned') is True
