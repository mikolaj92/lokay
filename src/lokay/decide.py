from lokay.legal import legal_admission, legal_after_code, legal_doctor

LEGALITY = {'admission': legal_admission, 'after_code': legal_after_code, 'doctor': legal_doctor}


def decide(decision_id, facts, *, post=None):
    options = LEGALITY[decision_id](facts)
    if len(options) == 1:
        return {'route': options[0], 'source': 'single_legal', 'calls': 0}
    if post is not None:
        post(options)
    return {'route': options[0], 'source': 'model', 'calls': 1 if post else 0}
