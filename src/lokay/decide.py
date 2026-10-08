class DecisionInfra(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


import hashlib
import json

from lokay.legal import legal_admission, legal_admit, legal_after_code, legal_disposition, legal_doctor, legal_failure, legal_pick, legal_stale

LEGALITY = {'admission': legal_admission, 'admit': legal_admit, 'after_code': legal_after_code, 'disposition': legal_disposition, 'doctor': legal_doctor, 'failure': legal_failure, 'pick': legal_pick, 'stale_pr': legal_stale}


def decide(decision_id, facts, *, post=None, cache=None, shadow=False, eval_passed=False):
    options = [item for item in LEGALITY[decision_id](facts) if eval_passed or item not in destructive_options(decision_id)]
    if not options:
        options = [catalog_abstain(decision_id)]
    if len(options) == 1:
        return {'route': options[0], 'source': 'single_legal', 'calls': 0}
    key = decision_id + ':' + hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()
    if cache is not None and key in cache:
        return {'route': cache[key], 'source': 'cache', 'calls': 0}
    try:
        answer = post(options) if post is not None else None
    except OSError as exc:
        raise DecisionInfra(str(exc)) from exc
    confidence = float((answer or {}).get('confidence', 1))
    if confidence <= 0.84:
        return {'route': catalog_abstain(decision_id), 'source': 'abstain', 'calls': 1}
    route = (answer or {}).get('route', options[0])
    if shadow:
        return {'route': catalog_abstain(decision_id), 'source': 'shadow', 'recorded': route, 'calls': 1}
    if cache is not None:
        cache[key] = route
    return {'route': route, 'source': 'model', 'calls': 1 if post else 0}

def catalog_abstain(decision_id):
    import pathlib
    text = pathlib.Path(__file__).with_name('decisions.toml').read_text()
    current = None
    found = None
    for line in text.splitlines():
        if line.startswith('id = '):
            current = line.split('"')[1]
        if line.startswith('on_abstain = ') and current == decision_id:
            found = line.split('"')[1]
    if found is None:
        raise KeyError(decision_id)
    return found

def destructive_options(decision_id):
    import pathlib
    text = pathlib.Path(__file__).with_name('decisions.toml').read_text()
    current = None
    for line in text.splitlines():
        if line.startswith('id = '):
            current = line.split('"')[1]
        if current == decision_id and line.startswith('destructive = '):
            return [part.strip().strip('"') for part in line.split('[', 1)[1].rstrip(']').split(',') if part.strip()]
    return []
