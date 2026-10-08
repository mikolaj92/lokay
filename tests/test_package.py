from lokay.nodes import BLUEPRINT, TICK, dispatch


def test_thirty_named_nodes_answer():
    assert len(TICK) == 13
    assert len(BLUEPRINT) == 17
    for name in TICK + BLUEPRINT:
        assert dispatch(name, {})['ok'] is True


def test_unknown_node_is_a_contract_failure():
    assert dispatch('merge', {})['terminal'] == 'contract_failed'
