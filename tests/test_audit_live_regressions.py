"""Regressions from the 2026-09-30 live audit, not green transport claims."""
from lokay.proc.delivery_closeout import triage
from lokay.proc.record_pass import classify_outcome
from lokay.proc.summarize_issue_to_pr import summarize


def test_closeout_observation_is_not_a_new_merge():
    replay = triage({'route': 'close', 'merged': True, 'intent': {'issue': 43}},
                    {'route': 'publish', 'issue_closed': True},
                    {'route': 'pending', 'confirmed': False,
                     'reason': 'receipt_provenance_incomplete'})
    assert replay['triage']['merged'] is False
    assert replay['triage']['merge_observed'] is True
    assert classify_outcome(prs=replay) == 'none'


def test_failed_delivery_preserves_named_cause():
    result = summarize(delivery={'route': 'failed', 'reason': 'invalid_coding_json_exhausted'},
                       closeout={}, no_effect={'reason': 'condition_not_met'})
    assert result['result']['reason'] == 'invalid_coding_json_exhausted'
    assert result['result']['delivered'] is False


def test_unattributed_replay_is_retired_without_fabricating_delivery(tmp_path, monkeypatch):
    from lokay.proc import delivery_closeout as dc
    from types import SimpleNamespace
    state = tmp_path / 'state.jsonl'
    intent = dc.prepare(state_path=state, repo='o/r', pr=58, issue=43,
                        branch='ai/fix/43', review={'decision': {'verdict': 'approve', 'reviewed_head_sha': 'a' * 40}},
                        tests={'ok': True, 'tested_head_sha': 'a' * 40}, live=True)['intent']
    monkeypatch.setattr(dc, 'observe', lambda **kw: {'route': 'close', 'merged': True, 'intent': intent})
    monkeypatch.setattr('lokay.config.load_config', lambda _: SimpleNamespace(state_path=state))
    monkeypatch.setattr('lokay.proc.publish_delivery_receipt.publish_from_config', lambda **kw: {
        'ok': True, 'route': 'pending', 'confirmed': False, 'terminal_unattributed': True,
        'reason': 'receipt_provenance_incomplete'})
    result = dc.publish(picked={}, config_path=None, live=True)
    assert result['confirmed'] is False
    assert dc.pending(state) == []
    import json
    events = [json.loads(line) for line in state.read_text().splitlines()]
    assert events[-1]['kind'] == 'delivery_closeout_unattributed'
    assert not any(event['kind'] == 'delivery_closeout_complete' for event in events)


def test_skipped_verification_is_not_a_transport_failure():
    from lokay.proc.local_verification_terminal import terminal
    result = terminal({'ok': True, 'route': 'not_applicable'})
    assert result['ok'] is True
    assert result['route'] == 'skip'
    assert result['status'] == 'skipped'


def test_retry_prompt_includes_valid_complete_implemented_example():
    from lokay.tool_contracts import render_contract
    import json
    prompt = render_contract('coding_retry', feedback='evidence_kind is only valid with needs_evidence', response='{}')
    example = next(line for line in prompt.splitlines() if line.startswith('{"verdict"'))
    from lokay.coding_boundary import parse_output
    assert parse_output(example)['evidence_kind'] is None
    assert json.loads(example)['verdict'] == 'implemented'


def test_historical_incomplete_provenance_does_not_replay_forever(tmp_path):
    from lokay.proc import delivery_closeout as dc
    state = tmp_path / 'state.jsonl'
    review = {'decision': {'verdict': 'approve', 'reviewed_head_sha': 'a' * 40}}
    intent = dc.prepare(state_path=state, repo='o/r', pr=58, issue=43,
                        branch='ai/fix/43', review=review,
                        tests={'ok': True, 'tested_head_sha': 'a' * 40}, live=True)['intent']
    from lokay.state import append_event
    append_event(state, {'kind': 'delivery_closeout_unattributed', 'repo': 'o/r', 'pr': 58,
                        'intent_sha256': intent['sha256'], 'reason': 'receipt_provenance_incomplete'}, durable=True)
    assert dc.pending(state) == []
    from lokay.state_compact import compact_state
    compact_state(state, min_bytes=0)
    assert dc.pending(state) == []


def test_delivery_terminal_preserves_coding_failure():
    from lokay.organ.coding_boundary import handle_coding_boundary
    result = handle_coding_boundary('summarize_issue_delivery', {}, {
        'coding_execution': {'route': 'fail_closed', 'reason': 'invalid_coding_json_exhausted'},
        'make_branch': {'branch': 'ai/fix/35'},
    }, {'repo': 'o/r', 'issue_number': 35})
    assert result['result']['reason'] == 'invalid_coding_json_exhausted'
    assert result['result']['delivered'] is False
