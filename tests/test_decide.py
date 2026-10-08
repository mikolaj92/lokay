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

def test_low_confidence_abstains():
    def post(options):
        return {'route': 'admit', 'confidence': 0.84}
    facts = {'free_slots': 1, 'W_global': 1, 'oldest_W_h': 1, 'doctor': 'ok', 'admitted_builds': 1, 'infra_1h': 0}
    out = decide('admission', facts, post=post, cache={})
    assert out['source'] == 'abstain'
    assert out['route'] == 'drain'

def test_transport_error_is_infra_not_abstain():
    from lokay.decide import DecisionInfra
    def post(options):
        raise OSError('down')
    facts = {'free_slots': 1, 'W_global': 1, 'oldest_W_h': 1, 'doctor': 'ok', 'admitted_builds': 1, 'infra_1h': 0}
    try:
        decide('admission', facts, post=post, cache={})
    except DecisionInfra as exc:
        assert exc.reason == 'down'
        return
    raise AssertionError('transport error was returned as a route')

def test_shadow_records_the_model_and_returns_abstain():
    def post(options):
        return {'route': 'admit', 'confidence': 0.99}
    facts = {'free_slots': 1, 'W_global': 1, 'oldest_W_h': 1, 'doctor': 'ok', 'admitted_builds': 1, 'infra_1h': 0}
    out = decide('admission', facts, post=post, shadow=True)
    assert out['source'] == 'shadow'
    assert out['route'] == 'drain'
    assert out['recorded'] == 'admit'

def test_destructive_option_is_not_sent_before_eval():
    sent = []
    facts = {'owner': '', 'subissues': False, 'task_lines': 0, 'open_pr': True, 'has_test': True, 'allow_untested': False, 'peers': ['other']}
    out = decide('admit', facts, post=sent.append, eval_passed=False)
    assert sent == []
    assert out['source'] == 'single_legal'
    wider = {'owner': '', 'subissues': False, 'task_lines': 0, 'open_pr': False, 'has_test': True, 'allow_untested': False, 'peers': ['other']}
    decide('admit', wider, post=sent.append, eval_passed=False)
    assert 'duplicate' not in sent[0] and 'not_actionable' not in sent[0]
