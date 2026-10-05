"""Select undecided inbox work for triage, never raw execution fuel."""

from lokay.proc.classify_issue_assignee import lokay_of
from lokay.proc.classify_open_issues import classify
from lokay.proc.pick_one_labeled import READY_LABELS
from lokay.proc.select_next_issue import occupied_repos_of, pick
from lokay.proc.walk_issue_leftover import identity, ownable, product_first, unoccupied
from lokay.triage import is_undecided


def select(listed: dict, last: dict | None = None, occupied=None) -> dict:
    classified = classify(listed)
    if classified['route'] != 'listed':
        return pick(classified)
    rows = [dict(row) for row in classified['issues']
            if identity(row) and not (set(row.get('labels') or []) & READY_LABELS)
            and is_undecided(row.get('labels') or [])]
    rows = unoccupied(ownable(product_first(rows), lokay_of(listed, last)),
                      occupied_repos_of(occupied))
    last = last or {}
    if 'leftover_issues' in last:
        # A slot's explicit empty tail means done, not restart within the pass.
        live = {identity(row): row for row in rows}
        rows = [live[key] for row in last['leftover_issues']
                if (key := identity(row)) in live]
    if not rows:
        return {'ok': True, 'route': 'none', 'reason': 'no_undecided_issue',
                'leftover': 0, 'leftover_issues': []}
    return pick({'route': 'listed', 'issues': rows})
