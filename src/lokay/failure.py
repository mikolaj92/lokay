"""Restart budget. Not imported by a runtime path."""


def classify(kind):
    if kind == 'timeout':
        return {'class': 'infra', 'infra': 'timeout'}
    if kind == 'malformed':
        return {'class': 'contract'}
    raise ValueError(kind)


def next_budget(budget, result):
    out = dict(budget)
    out['call_failure_decision'] = False
    if result['class'] == 'infra':
        out['infra_24h'] = budget['infra_24h'] + 1
        out['call_failure_decision'] = out['infra_24h'] >= 4
    return out

def repo_backoff_seconds(failed_runs):
    if failed_runs < 3:
        return 0
    return min(60 * 2 ** (failed_runs - 3), 6 * 60 * 60)
