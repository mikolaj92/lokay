import hashlib
import json

from lokay.legal import legal_admission, legal_after_code, legal_doctor

LEGALITY = {'admission': legal_admission, 'after_code': legal_after_code, 'doctor': legal_doctor}


def decide(decision_id, facts, *, post=None, cache=None):
    options = LEGALITY[decision_id](facts)
    if len(options) == 1:
        return {'route': options[0], 'source': 'single_legal', 'calls': 0}
    key = decision_id + ':' + hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()
    if cache is not None and key in cache:
        return {'route': cache[key], 'source': 'cache', 'calls': 0}
    if post is not None:
        post(options)
    route = options[0]
    if cache is not None:
        cache[key] = route
    return {'route': route, 'source': 'model', 'calls': 1 if post else 0}
