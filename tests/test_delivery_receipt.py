import pytest
from lokay.delivery_receipt import marker, parse_marker, verify_receipt, finalize_receipt


def base(): return {'repo':'a/b','issue':7,'work_id':'a/b#7','graph_digest':'g','path_digest':'p','run_refs':['r'],'builder_session':'b','reviewer_session':'v','acceptance_digest':'a','head_sha':'h'}

def test_one_canonical_marker_roundtrips_without_prompts_or_secrets():
    text=marker(base()); parsed=parse_marker('body\n'+text+'\n')
    assert parsed['head_sha']=='h' and text.count('lokay-autonomous-delivery:')==1
    assert 'prompt' not in text and 'token' not in text

def test_manual_or_tampered_pr_is_not_autonomous():
    assert parse_marker('manual') is None
    with pytest.raises(ValueError,match='digest|head'):
        verify_receipt({**base(),'head_sha':'x'},observed_head='h')

def test_final_receipt_requires_main_merge_and_closed_issue():
    complete=finalize_receipt(base(),merge_sha='m',merged_at='t',issue_closed=True,main_contains_head=True)
    assert verify_receipt(complete,observed_head='h',require_delivered=True)['autonomous']
    with pytest.raises(ValueError,match='delivery'):
        finalize_receipt(base(),merge_sha='m',merged_at='t',issue_closed=False,main_contains_head=True)
