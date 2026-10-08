"""Restart budget. Not imported by a runtime path."""


def classify(kind):
    if kind == 'timeout':
        return {'class': 'infra', 'infra': 'timeout'}
    if kind == 'malformed':
        return {'class': 'contract'}
    if kind == 'inconclusive':
        return {'class': 'inconclusive'}
    raise ValueError(kind)


def due(item, *, now, stall_h=24, paused_h=0):
    """One stall fact. Held and human-owned states are owned elsewhere."""
    if item['state'] in {'held', 'needs_human', 'parked', 'human_owned'}:
        return None
    quiet_h = (now - item['last_progress']) / 3600 - paused_h
    if quiet_h < stall_h:
        return None
    return {'kind': 'stalled', 'work_id': item['work_id'], 'since': item['last_progress'], 'last_head_sha': item['head_sha']}


def no_merge(queue, *, now, alarm_h=6, paused_h=0):
    """One factory alarm. An empty queue or paused hours do not count."""
    if alarm_h <= 0 or not queue['depth']:
        return None
    quiet_h = (now - max(queue['last_merge'], queue['last_publish'])) / 3600 - paused_h
    if quiet_h < alarm_h:
        return None
    return {'kind': 'factory_stalled', 'since': max(queue['last_merge'], queue['last_publish']), 'queue': queue['depth']}


def next_budget(budget, result, *, gb10_up=True):
    out = dict(budget)
    out['call_failure_decision'] = False
    if not gb10_up:
        return out
    if result['class'] == 'infra':
        out['infra_24h'] = budget['infra_24h'] + 1
        out['call_failure_decision'] = out['infra_24h'] >= 4
    return out

def repo_backoff_seconds(failed_runs):
    if failed_runs < 3:
        return 0
    return min(60 * 2 ** (failed_runs - 3), 6 * 60 * 60)
