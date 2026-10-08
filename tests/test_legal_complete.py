import itertools

from lokay.legal import legal_admission, legal_disposition, legal_doctor, legal_failure, legal_lenses, legal_stale


def test_no_reachable_state_has_empty_legal_set():
    domains = {
        legal_admission: {'free_slots': (0, 1), 'W_global': (0, 5), 'oldest_W_h': (1, 80), 'doctor': ('ok', 'pause'), 'admitted_builds': (0, 1), 'infra_1h': (0, 3)},
        legal_doctor: {'probes_green': (True, False), 'hard_red': (True, False), 'behind': (0, 1), 'ahead': (0, 1), 'dirty': (True, False), 'lease_held': (True, False), 'stale_worktrees': (True, False)},
        legal_failure: {'within_budget': (True, False), 'klass': ('infra', 'contract'), 'infra_attempts': (0, 6), 'crash_loop': (True, False), 'decided_this_episode': (True, False)},
        legal_stale: {'base_moved': (True, False), 'lease_free': (True, False), 'refreshes': (0, 2), 'owner_silent_days': (6, 7), 'age_days': (14, 15)},
        legal_disposition: {'veto': (True, False), 'review_round': (0, 2), 'review_rounds_max': (2,), 'issue_closed': (True, False), 'superseded': (True, False)},
        legal_lenses: {'docs_only': (True, False)},
    }
    for fn, domain in domains.items():
        keys = list(domain)
        for values in itertools.product(*(domain[key] for key in keys)):
            assert fn(dict(zip(keys, values))), fn.__name__
