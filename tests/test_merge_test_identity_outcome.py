from lokay.proc.select_pr_triage_outcome import select


def test_unverified_local_head_is_wait_not_approve_green():
    result = select({'route': 'review', 'head_sha': 'a'*40}, {'route': 'continue'},
                    {'ok': False, 'skipped': True, 'waiting': True,
                     'reason': 'merge_test_identity_unverified',
                     'error': 'local test head differs from reviewed head'})
    assert result['route'] == 'wait'
    assert result['reason'] == 'merge_test_identity_unverified'
    assert result['waiting'] is True
