"""Completed provenance, not merely a checksummed provisional marker."""
import pytest

from lokay.delivery_receipt import (
    finalize_receipt,
    marker,
    parse_marker,
    signed,
    verify_receipt,
)
from lokay.proc.publish_delivery_receipt import publish


def completed_lineage():
    return {
        'repo': 'o/r', 'issue': 42, 'work_id': 'o/r#42', 'branch': 'ai/fix/42',
        'head_sha': 'b' * 40, 'graph_digest': 'sha256:' + '1' * 64,
        'path_digest': 'sha256:' + '2' * 64, 'acceptance_digest': 'sha256:' + '3' * 64,
        'acceptance_identity': 'o/r#42', 'acceptance_accepted': True,
        'builder_session': 'builder-session-42', 'reviewer_session': 'vendor-run-57',
        'run_refs': [{'db': '/tmp/build.sqlite', 'run_id': 'build-42', 'path_id': 'coding_execution'}],
        'reviewed_head_sha': 'b' * 40, 'tested_head_sha': 'b' * 40,
        'review_result_sha256': '4' * 64, 'task_identity_sha256': '5' * 64,
        'test_run_ref': {'db': '/tmp/test.sqlite', 'run_id': 'test-42', 'path_id': 'test_local_execution'},
    }


@pytest.mark.parametrize('damage', [None, 'builder_session', 'reviewer_session', 'graph_digest',
                                   'path_digest', 'acceptance_digest', 'acceptance_identity',
                                   'acceptance_accepted', 'run_refs', 'test_run_ref', 'reviewed_head_sha',
                                   'run_ref_pending', 'run_ref_unavailable', 'test_ref_pending',
                                   'builder_unavailable', 'acceptance_missing', 'tested_head_sha'])
def test_final_confirmation_rejects_provisional_evidence(damage):
    receipt = completed_lineage()
    if damage == 'run_ref_pending':
        receipt['run_refs'][0]['run_id'] = 'pending'
    elif damage == 'run_ref_unavailable':
        receipt['run_refs'][0]['db'] = 'unavailable'
    elif damage == 'test_ref_pending':
        receipt['test_run_ref']['run_id'] = 'pending'
    elif damage == 'builder_unavailable':
        receipt['builder_session'] = 'unavailable'
    elif damage == 'acceptance_missing':
        receipt.pop('acceptance_identity')
    elif damage:
        receipt[damage] = {'acceptance_accepted': False, 'run_refs': [], 'test_run_ref': {},
                           'acceptance_identity': 'other/repo#42',
                           'reviewed_head_sha': 'a' * 40}.get(damage, 'pending')
    # Provisional serialization is permitted, but a valid checksum is not completion.
    assert parse_marker(marker(receipt)) is not None
    forged_completion = signed({**receipt, 'merge_sha': 'c' * 40, 'merged_at': '2026-09-21',
                                'issue_closed': True, 'main_contains_head': True})
    if damage:
        with pytest.raises(ValueError, match='provenance'):
            verify_receipt(forged_completion, observed_head='b' * 40, require_delivered=True)
        with pytest.raises(ValueError, match='provenance'):
            finalize_receipt(receipt, merge_sha='c' * 40, merged_at='2026-09-21',
                             issue_closed=True, main_contains_head=True)
    else:
        assert verify_receipt(forged_completion, observed_head='b' * 40, require_delivered=True)


@pytest.mark.parametrize('route', ['direct', 'retry', 'evidence'])
def test_native_coding_producer_to_default_pr_marker(tmp_path, monkeypatch, route):
    import hashlib
    import json
    import sys
    import tomllib
    from pathlib import Path

    from test_issue_triage_fala import base_effector

    from lokay.graph_run import find_default_package, run_path
    from lokay.organ.publication import handle_publication
    from lokay.proc import coding_execution_subflow

    # Only the external coding slot is replaced. All coding reducers and the
    # child wrapper are real; the parent publication consumer receives that output.
    script = tmp_path / 'coding.py'
    script.write_text(base_effector('route = ' + repr(route) + '\n' + '''
from lokay.organ.coding_boundary import handle_coding_boundary
from lokay.organ.common import _conduction_values
if a in {'run_agent', 'coding_retry_agent', 'evidence_coding_agent'}:
    text = json.dumps({'verdict':'implemented','evidence_kind':None,'summary':'done','tests_run':[],'residual_risk':''})
    if a == 'run_agent' and route == 'retry': text = 'invalid JSON'
    if a == 'run_agent' and route == 'evidence':
        text = json.dumps({'verdict':'needs_evidence','evidence_kind':'localized_diff','summary':'need','tests_run':[],'residual_risk':''})
    v.update(status='completed', session='executor-session-' + a, stdout=text)
elif a == 'collect_coding_localized_diff':
    v.update(evidence='temporary diff')
else:
    from fala.sdk import declared_inputs
    v = handle_coding_boundary(a, dict(declared_inputs(m)), _conduction_values(m), {})
'''))
    source = find_default_package()
    text = source.read_text()
    package = tomllib.loads(text)
    coding = next(p for p in package['correlation_paths'] if p['id'] == 'coding_execution')
    # Replace subprocess adapters, not the graph's conduction or gates.
    import re
    sections = text.split('[[correlation_paths]]')
    for i, section in enumerate(sections):
        if section.lstrip().startswith('id = "coding_execution"'):
            sections[i] = re.sub(r'^adapter = .*$',
                'adapter = { kind = "subprocess", command = ' + json.dumps([sys.executable, str(script)]) + ' }',
                section, flags=re.MULTILINE)
    custom = tmp_path / 'package.toml'
    custom.write_text('[[correlation_paths]]'.join(sections))
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setattr(coding_execution_subflow, 'run_path',
                        lambda **kw: run_path(**kw, package_path=custom, db_path=tmp_path / 'coding'))
    child = coding_execution_subflow.run(config_path=None, live=False,
        extra_inputs={'repo':'o/r', 'issue':42, 'branch':'ai/fix/42', 'worktree':str(tmp_path),
                      'localize':{'paths':['code.py']}})
    assert child['route'] == 'implemented', json.dumps(child)
    selected_agent = {'direct':'run_agent', 'retry':'coding_retry_agent', 'evidence':'evidence_coding_agent'}[route]
    assert child.get('session') == 'executor-session-' + selected_agent
    assert child['run_refs'][0]['path_id'] == 'coding_execution'
    assert Path(child['run_refs'][0]['db']).is_file()
    assert child['graph_digest'] == 'sha256:' + hashlib.sha256(custom.read_bytes()).hexdigest()
    expected_path = next(p for p in tomllib.loads(custom.read_text())['correlation_paths'] if p['id'] == coding['id'])
    assert child['path_digest'] == 'sha256:' + hashlib.sha256(json.dumps(expected_path, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    captured = {}
    def create(**kw):
        captured.update(kw)
        return {'ok':True, 'pr':57}
    monkeypatch.setattr('lokay.proc.pr_create_subflow.run', create)
    upstream = {'get_issue':{'issue':{'repo':'o/r','number':42,'title':'deliver','body':''}},
                'make_branch':{'branch':'ai/fix/42'}, 'coding_execution':child,
                'finalize_local_tests':{'ok':True,'route':'publish'},
                'assert_real_diff':{'ok':True}, 'push':{'ok':True,'head_sha':'b'*40},
                'finalize_acceptance':{'ok':True,'accepted':True,'route':'publish',
                                       'acceptance_digest':'sha256:'+'3'*64,'identity':'o/r#42'},
                'select_publish_gate':{'ok':True,'route':'publish'}}
    result = handle_publication('pr_create', {'live':False}, upstream,
                               {'cfg':[], 'live':[], 'repo':'o/r', 'issue_number':42,
                                'pr_number':None, 'repair_mode':False, 'branch':'ai/fix/42'})
    assert result is not None
    assert result['ok'], result
    receipt = parse_marker(captured['body'])
    assert receipt is not None
    assert receipt['builder_session'] == child['session']
    for key in ('graph_digest','path_digest','run_refs'):
        assert receipt[key] == child[key]
    assert receipt['acceptance_identity'] == 'o/r#42'
    assert receipt['acceptance_accepted'] is True
    assert receipt['acceptance_digest'] == upstream['finalize_acceptance']['acceptance_digest']
    assert receipt['reviewer_session'] == 'pending'  # Still provisional before review.


@pytest.mark.parametrize('length', ['under', 'over', 'beyond'])
def test_coding_result_survives_transport_tail(tmp_path, monkeypatch, length):
    import json
    import sys

    from lokay.agent import run_agent
    from lokay.config import Config
    from lokay.runner import Runner

    summary = {'under': 100, 'over': 5000, 'beyond': 250_000}[length]
    summary = 'x' * summary
    script = tmp_path / 'executor.py'
    script.write_text('import json\nprint(json.dumps(' + repr(
        {'verdict': 'implemented', 'evidence_kind': None, 'summary': summary,
         'tests_run': ['pytest'], 'residual_risk': 'none'}) + '))\n')
    cfg = Config(agent='local-executor', agent_command=sys.executable,
                 agent_args=[str(script)], executor_enabled=True)
    envelope = run_agent(Runner(), cfg, worktree=tmp_path, prompt='edit',
                         execute=True, session_kind='code', attach_collector_boundary=False)
    from lokay.organ.coding_boundary import handle_coding_boundary
    validated = handle_coding_boundary('validate_coding_result', {'worktree': str(tmp_path)},
                                       {'run_agent': envelope}, {})
    if length == 'beyond':
        assert validated['route'] == 'fail_closed', validated
        assert validated['reason'] == 'coding_result_truncated'
        return
    assert validated['route'] == 'valid', validated
    assert validated['decision']['summary'] == summary


@pytest.mark.parametrize('binding', ['argument', 'embedded', 'absent', 'prompt_only'])
def test_real_executor_session_binding_to_receipt(tmp_path, monkeypatch, binding):
    import json
    import sys

    from lokay.agent import run_agent, session_id_for_worktree
    from lokay.config import Config
    from lokay.organ.coding_boundary import handle_coding_boundary
    from lokay.runner import Runner

    monkeypatch.delenv('LOKAY_AGENT', raising=False)
    script = tmp_path / 'executor.py'
    # A local executor consumes its session argument and records the binding.
    # It returns no session in generated JSON: provenance must come from the
    # trusted invocation, not model-authored text or a worktree-derived guess.
    script.write_text('''import argparse, json, pathlib
parser = argparse.ArgumentParser()
parser.add_argument('--session-id')
parser.add_argument('--prompt')
args = parser.parse_args()
pathlib.Path('bound-session.txt').write_text(args.session_id or '')
print(json.dumps({'verdict': 'implemented', 'evidence_kind': None, 'summary': 'done', 'tests_run': [], 'residual_risk': ''}))
''')
    args = [str(script)]
    if binding == 'argument':
        args += ['--session-id', '{session}']
    elif binding == 'embedded':
        args += ['--session-id={session}']
    elif binding == 'prompt_only':
        args += ['--prompt', '{prompt}']
    cfg = Config(agent='local-executor', agent_command=sys.executable,
                 agent_args=args, executor_enabled=True)
    expected = session_id_for_worktree(tmp_path, kind='probe')
    envelope = run_agent(Runner(), cfg, worktree=tmp_path, prompt=expected,
                         execute=True, session_kind='probe', attach_collector_boundary=False)
    assert envelope['status'] == 'completed', envelope
    assert json.loads(envelope['stdout_tail'])['verdict'] == 'implemented'
    bound = binding in {'argument', 'embedded'}
    assert (tmp_path / 'bound-session.txt').read_text() == (expected if bound else '')
    validated = handle_coding_boundary('validate_coding_result', {'worktree': str(tmp_path)},
                                      {'run_agent': envelope}, {})
    assert validated is not None and validated['route'] == 'valid'
    receipt = completed_lineage()
    receipt['builder_session'] = validated.get('session', '')
    if bound:
        assert receipt['builder_session'] == expected
        completed = finalize_receipt(receipt, merge_sha='c' * 40, merged_at='2026-09-21',
                                     issue_closed=True, main_contains_head=True)
        assert verify_receipt(completed, observed_head='b' * 40, require_delivered=True)
    else:
        with pytest.raises(ValueError, match='provenance'):
            finalize_receipt(receipt, merge_sha='c' * 40, merged_at='2026-09-21',
                             issue_closed=True, main_contains_head=True)
        assert not envelope.get('session')
        assert not validated.get('session')


@pytest.mark.parametrize('session', ['fixture-run-1', None, 'pending', 'unavailable'])
def test_vendor_run_identity_reaches_completed_marker(tmp_path, session):
    import hashlib
    import json

    from test_pr_review_validation import FIXTURES, _request

    from lokay.config import Config
    from lokay.proc.publish_pr_review import publish as publish_review
    from lokay.proc.validate_pr_review import validate_result

    request = json.loads(json.dumps(_request()))  # Real subprocess wire uses arrays.
    from lokay_review_open_code_review.contract import normalize_result
    upstream = json.loads((FIXTURES / 'review-complete.json').read_text())
    upstream['comments'] = []
    upstream['summary']['comments'] = 0
    upstream['manifest']['run_id'] = session
    upstream['manifest']['repository']['identity_sha256'] = hashlib.sha256(b'github.com/acme/demo').hexdigest()
    result = normalize_result(request, upstream, engine={**request['engine'],
        'name':'open-code-review', 'version':'v1.12.7'}, changed_ranges=request['changed_ranges'])
    selected = validate_result(result, request)
    assert selected['route'] == 'valid'
    cfg = Config(pr_review_artifacts_dir=tmp_path / 'reviews',
                 pr_review_config_sha256='9'*64, pr_review_binary_sha256='f'*64,
                 pr_review_binary_version='v1.12.7', pr_review_provider='example-provider',
                 pr_review_model='example-model')
    reviewed = publish_review(cfg=cfg, repo='acme/demo', pr=84, evidence=request,
                              selected={**selected, 'route':'publish'}, live=False)
    assert reviewed['merge_ok'] is True
    # The durable artifact/cache boundary must preserve the same vendor identity.
    from lokay.proc.pr_review_artifacts import load_verified_result
    artifact_path, = (tmp_path / 'reviews').rglob('*.json')
    cached = load_verified_result(cfg=cfg, repo='acme/demo', pr=84, head_sha='b'*40,
        artifact_sha256=hashlib.sha256(artifact_path.read_bytes()).hexdigest(), evidence=request)
    assert cached is not None
    assert cached['decision']['review_evidence'].get('run_id') == session
    cached_publication = publish_review(cfg=cfg, repo='acme/demo', pr=84, evidence=request,
        selected={'route':'cached', 'decision':cached['decision'], 'merge_ok':True}, live=False)
    assert cached_publication['decision']['review_evidence'].get('run_id') == session
    reviewed = cached_publication
    receipt = completed_lineage()
    receipt.update(repo='acme/demo', work_id='acme/demo#42', acceptance_identity='acme/demo#42',
                   branch='ai/fix/42-demo', reviewer_session='pending')
    edits = []
    out = publish(repo='acme/demo', pr=84, issue=42, merge={'merged':True}, close={}, live=True,
        review=reviewed, tests={'ok':True,'tested':True,'tested_head_sha':'b'*40, **receipt['test_run_ref']},
        read_pr=lambda *_: {'body':marker(receipt), 'headRefOid':'b'*40,
                           'headRefName':receipt['branch'], 'headRepository':{'nameWithOwner':'acme/demo'},
                           'state':'MERGED', 'baseRefName':'main',
                           'mergeCommit':{'oid':'c'*40}, 'mergedAt':'2026-09-21'},
        read_issue=lambda *_: {'state':'CLOSED'}, main_contains=lambda *_: True,
        edit_pr=lambda *args: edits.append(args))
    assert out['confirmed'] is (session == 'fixture-run-1'), out
    if session == 'fixture-run-1':
        assert result['evidence']['run_id'] == session
        assert out['receipt']['reviewer_session'] == session
        assert out['receipt']['review_result_sha256'] == reviewed['decision']['review_result_sha256']
        assert verify_receipt(out['receipt'], observed_head='b'*40, require_delivered=True)
    else:
        assert out['reason'] == 'receipt_provenance_incomplete'
        assert not edits


def test_acceptance_producer_retains_identity_through_final_reducer(tmp_path):
    from lokay.acceptance import prepare_acceptance, verify_acceptance
    from lokay.proc.finalize_acceptance import finalize
    artifact = prepare_acceptance({'repo':'o/r','number':42}, root=tmp_path,
                                  evidence=[{'kind':'test','expect':'green'}])
    accepted = verify_acceptance(artifact['path'], [{'kind':'test','ok':True}], artifact['digest'])
    for first, recheck in ((accepted, {}), ({'accepted':False}, accepted)):
        out = finalize(first, recheck)
        assert out['identity'] == 'o/r#42'
        assert out['acceptance_digest'] == artifact['digest']
        assert out['accepted'] is True


def test_publication_leaves_incomplete_provenance_pending():
    receipt = completed_lineage()
    receipt['builder_session'] = 'unavailable'
    out = publish(repo='o/r', pr=57, issue=42, merge={'merged': True}, close={}, live=True,
                  read_pr=lambda *_: {'body': marker(receipt), 'headRefOid': 'b' * 40,
                                     'mergeCommit': {'oid': 'c' * 40}, 'mergedAt': '2026-09-21'},
                  read_issue=lambda *_: {'state': 'CLOSED'}, main_contains=lambda *_: True,
                  edit_pr=lambda *_: pytest.fail('incomplete provenance must not be published'))
    assert out['confirmed'] is False
    assert out['reason'] == 'receipt_provenance_incomplete'
    assert out['issue_closed'] is True
