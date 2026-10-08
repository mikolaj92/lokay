from lokay.proc.review_repair_gate import route_review_repair


def test_infra_failure_is_not_a_product_repair():
    out = route_review_repair({'decision': {'verdict': 'infra_failure', 'reason': 'tools_allowlist_invalid'}})
    assert out['route'] == 'infra'
    assert out['reason'] == 'tools_allowlist_invalid'


def test_request_changes_still_repairs():
    decision = {
        'verdict': 'request_changes', 'task': {'type': 'Issue', 'state': 'OPEN'},
        'findings': [{'path': 'a.py'}], 'reviewed_head_sha': 'a'*40,
        'task_identity_sha256': 'b'*64, 'review_result_sha256': 'c'*64,
    }
    assert route_review_repair({'decision': decision})['route'] == 'repair'
