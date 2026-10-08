from lokay.failure import classify, next_budget


def test_timeout_is_infra_and_does_not_spend_review():
    assert classify('timeout') == {'class': 'infra', 'infra': 'timeout'}
    budget = next_budget({'infra_24h': 0, 'review': 2}, classify('timeout'))
    assert budget['infra_24h'] == 1
    assert budget['review'] == 2


def test_fourth_infra_failure_needs_a_human():
    budget = next_budget({'infra_24h': 3, 'review': 2}, classify('timeout'))
    assert budget['call_failure_decision'] is True


def test_malformed_code_is_contract_and_cannot_retry():
    assert classify('malformed') == {'class': 'contract'}

def test_gb10_down_does_not_move_the_budget():
    budget = {'infra_24h': 0, 'review': 2}
    out = next_budget(budget, classify('timeout'), gb10_up=False)
    assert out['infra_24h'] == 0
    assert out['call_failure_decision'] is False
