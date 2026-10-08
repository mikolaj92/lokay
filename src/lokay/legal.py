"""Pure legality filters. Not imported by a runtime path."""


def legal_admission(facts):
    options = ['drain']

def legal_plan_gate(facts):
    if facts.get('plan_gate', 'off') == 'off':
        return ['proceed']
    options = ['proceed', 'needs_human']
    if not facts.get('replanned'):
        options.insert(1, 'replan')
    return options

    blocked = (
        facts['free_slots'] == 0
        or facts['W_global'] >= 5
        or facts['oldest_W_h'] > 72
        or facts['doctor'] != 'ok'
        or facts['admitted_builds'] == 0
    )
    if not blocked:
        options.append('admit')
    if facts['doctor'] != 'ok' or facts['infra_1h'] >= 3:
        options.append('pause')
    return options

def legal_after_code(facts):
    options = ['needs_human']
    publish = facts['diff_nonempty'] and not facts['secrets_hit'] and not facts['conflict_markers'] and facts['status'] == 'implemented' and (facts['exit'] == 0 or (not facts['declared'] and facts['allow_untested']))
    repair = facts['fix_budget'] > 0 and (facts['exit'] != 0 or not facts['diff_nonempty'] or facts['secrets_hit'] or facts['conflict_markers'])
    if publish:
        options.append('publish')
    if repair:
        options.append('repair')
    if facts['status'] == 'cannot':
        options.append('abandon')
    return options


def legal_doctor(facts):
    """D9. A red probe, including merge plumbing, makes ok illegal (#1627).

    host_ff is legal only when the checkout is strictly behind, clean, and unleased.
    """
    if facts['probes_green']:
        return ['ok']
    options = ['wait', 'pause']
    if facts['behind'] > 0 and facts['ahead'] == 0 and not facts['dirty'] and not facts['lease_held'] and not facts['hard_red']:
        options.append('host_ff')
    if facts['stale_worktrees'] and not facts['hard_red']:
        options.append('reap_worktrees')
    return options

def legal_failure(facts):
    """D8. trigger is failure, stall, no_merge, or inconclusive (#1626)."""
    trigger = facts.get('trigger', 'failure')
    if trigger == 'stall':
        if int(facts.get('stall_episode') or 1) <= 1:
            return ['needs_human', 'retry_later']
        return ['needs_human']
    if trigger in {'no_merge', 'inconclusive'}:
        if int(facts.get('episode') or 1) <= 1:
            return ['needs_human', 'retry_later']
        return ['needs_human']
    if facts.get('klass') == 'contract':
        return ['needs_human']
    if facts['within_budget']:
        return ['retry_later']
    options = ['needs_human']
    if facts['klass'] == 'infra' and facts['infra_attempts'] < 6:
        options.append('retry_later')
    if facts['crash_loop'] and not facts['decided_this_episode']:
        options.append('quarantine_repo')
    return options


def legal_stale(facts):
    options = ['wait']
    if facts['base_moved'] and facts['lease_free'] and facts['refreshes'] < 2:
        options.append('refresh')
    if facts['owner_silent_days'] >= 7 and facts['age_days'] > 14:
        options.append('close_pr')
    return options

def legal_admit(facts):
    if facts['owner'] == 'skip' or facts['subissues'] or facts['task_lines'] >= 2:
        return ['not_actionable']
    if facts['owner'] == 'build':
        return ['build']
    options = ['needs_human']
    if not facts['open_pr'] and (facts['has_test'] or facts['allow_untested']):
        options.append('build')
    if facts['peers']:
        options.append('duplicate')
    if facts['owner'] != 'build':
        options.append('not_actionable')
    return options


def legal_pick(facts):
    legal = []
    for item in facts['candidates']:
        if not item['lease_free'] or item['quarantine'] or item['backoff'] or item['restarts_left'] <= 0:
            continue
        if item['kind'] == 'obligation' or (facts['admission'] == 'admit' and item['W_repo'] < 2 and not facts['obligation_waiting']):
            legal.append(item['id'])
    return (legal or ['none'])[:8] + (['none'] if legal else [])


def legal_disposition(facts):
    """D7 options. `ready` is the old `ready_for_human` (#1625).

    `repair` needs a blocking finding or a hard fact, a round still left,
    and progress since the previous round. A grade below its bar is not a veto.
    """
    options = ['needs_human']
    if _ready(facts):
        options.append('ready')
    if _repair(facts):
        options.append('repair')
    if facts.get('issue_closed') or facts.get('superseded'):
        options.append('close_pr')
    return options


def _ready(facts):
    if facts.get('veto') or facts.get('blocking') or facts.get('hard_fact') or facts.get('owner_changes'):
        return False
    if int(facts.get('review_round') or 0) >= int(facts.get('review_rounds_max') or 3):
        return False
    if facts.get('behavior_change') and facts.get('swarm') != 'green':
        return False
    if len(facts.get('abstained') or []) >= 2:
        return False
    return True


def _repair(facts):
    if facts.get('owner_changes'):
        return False
    if int(facts.get('review_round') or 0) >= int(facts.get('review_rounds_max') or 3):
        return False
    if not facts.get('blocking') and not facts.get('hard_fact'):
        return False
    if int(facts.get('review_round') or 0) >= 2 and not facts.get('progress', True):
        return False
    return True

LENSES = ('scope', 'correctness', 'security', 'production', 'alignment', 'testing', 'architecture')


def legal_lenses(facts):
    if facts['docs_only']:
        return ['scope', 'correctness']
    return list(LENSES)
