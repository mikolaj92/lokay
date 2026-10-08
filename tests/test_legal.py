from lokay.legal import legal_admission


def test_full_queue_cannot_admit():
    assert legal_admission({'free_slots': 0, 'W_global': 1, 'oldest_W_h': 1, 'doctor': 'ok', 'admitted_builds': 1, 'infra_1h': 0}) == ['drain']


def test_healthy_queue_can_admit():
    assert 'admit' in legal_admission({'free_slots': 1, 'W_global': 1, 'oldest_W_h': 1, 'doctor': 'ok', 'admitted_builds': 1, 'infra_1h': 0})
