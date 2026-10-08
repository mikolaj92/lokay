from lokay.decide import decide


def test_single_legal_makes_no_http_call():
    calls = []
    out = decide('admission', {'free_slots': 0, 'W_global': 1, 'oldest_W_h': 1, 'doctor': 'ok', 'admitted_builds': 1, 'infra_1h': 0}, post=calls.append)
    assert out == {'route': 'drain', 'source': 'single_legal', 'calls': 0}
    assert calls == []

def test_same_facts_call_once():
    calls = []
    cache = {}
    facts = {'free_slots': 1, 'W_global': 1, 'oldest_W_h': 1, 'doctor': 'ok', 'admitted_builds': 1, 'infra_1h': 0}
    first = decide('admission', facts, post=calls.append, cache=cache)
    second = decide('admission', facts, post=calls.append, cache=cache)
    assert first['source'] == 'model'
    assert second['source'] == 'cache'
    assert len(calls) == 1
