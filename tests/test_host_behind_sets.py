from lokay.proc.select_repair_route import _SOFT_HEALTH
from lokay.recovery_history import _NON_FAILURE_HEALTH


def test_host_behind_is_not_a_failure_in_either_set():
    assert 'host_behind' in _SOFT_HEALTH
    assert 'host_behind' in _NON_FAILURE_HEALTH
