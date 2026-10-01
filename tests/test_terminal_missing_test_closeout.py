import json
from lokay.proc.delivery_closeout import prepare, publish, pending
import pytest


@pytest.mark.parametrize('reason,terminal', [
    ('receipt_review_test_unverified', True),
    ('delivery_publication_failed', False),
])
def test_merged_skipped_test_intent_terminates_without_fake_receipt(tmp_path, monkeypatch, reason, terminal):
    import lokay.proc.delivery_closeout as closeout
    import lokay.proc.publish_delivery_receipt as receipt
    state = tmp_path / 'state.jsonl'
    cfg = tmp_path / 'config.yaml'
    cfg.write_text(f'state:\n  path: {state}\nrepos: []\n')
    head = 'a'*40
    review = {'decision': {'verdict': 'approve', 'reviewed_head_sha': head}}
    tests = {'ok': True, 'tested': False, 'skipped': True, 'reason': 'no_declared_test', 'tested_head_sha': head}
    intent = prepare(state_path=state, repo='o/r', pr=43, issue=35, branch='ai/fix/35', review=review, tests=tests, live=True)['intent']
    monkeypatch.setattr(closeout, 'observe', lambda **kw: {'route': 'close', 'merged': True, 'intent': intent})
    monkeypatch.setattr(receipt, 'publish_from_config', lambda **kw: {'ok': True, 'route': 'pending', 'confirmed': False, 'reason': reason})
    result = publish(picked={}, config_path=str(cfg), live=True)
    assert result['confirmed'] is False
    if not terminal:
        assert pending(state) == [intent]
        return
    assert pending(state) == []
    event = json.loads(state.read_text().splitlines()[-1])
    assert event['kind'] == 'delivery_closeout_unattributed'
    assert event['reason'] == 'receipt_review_test_unverified'
