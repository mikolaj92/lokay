from lokay.legal import legal_admission


def test_full_queue_cannot_admit():
    assert legal_admission({'free_slots': 0, 'W_global': 1, 'oldest_W_h': 1, 'doctor': 'ok', 'admitted_builds': 1, 'infra_1h': 0}) == ['drain']


def test_healthy_queue_can_admit():
    assert 'admit' in legal_admission({'free_slots': 1, 'W_global': 1, 'oldest_W_h': 1, 'doctor': 'ok', 'admitted_builds': 1, 'infra_1h': 0})

def test_contract_failure_cannot_retry():
    from lokay.legal import legal_failure
    assert legal_failure({'within_budget': False, 'klass': 'contract', 'infra_attempts': 0, 'crash_loop': False, 'decided_this_episode': False}) == ['needs_human']


def test_stale_pr_can_close_when_owner_is_silent():
    from lokay.legal import legal_stale
    assert 'close_pr' in legal_stale({'base_moved': False, 'lease_free': True, 'refreshes': 0, 'owner_silent_days': 7, 'age_days': 15})
