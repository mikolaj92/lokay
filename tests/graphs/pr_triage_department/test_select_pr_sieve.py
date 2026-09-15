"""select_pr_sieve in pr_triage_department: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'pr_triage_department'
_NODE_ID = 'select_pr_sieve'
_ATOM = 'select_pr_sieve'
_CONDUCTION = ['list_pr_sieve']
_WHEN = None
_REQUIRED_WHEN_FIELDS = ['route']
_EFFECTORS = [
    {'conduction': [], 'id': 'list_pr_sieve', 'when': None},
    {'conduction': ['list_pr_sieve'], 'id': 'select_pr_sieve', 'when': None},
    {'conduction': ['select_pr_sieve'], 'id': 'reconcile_pr_repair_push', 'when': None},
    {'conduction': ['reconcile_pr_repair_push'], 'id': 'run_pr_sieve',
     'when': {'equals': 'review', 'path': 'route', 'upstream': 'reconcile_pr_repair_push'}},
    {'conduction': ['select_pr_sieve', 'reconcile_pr_repair_push', 'run_pr_sieve'],
     'id': 'select_pr_triage_verdict', 'when': None},
    {'conduction': ['select_pr_sieve', 'reconcile_pr_repair_push', 'run_pr_sieve',
                    'select_pr_triage_verdict'],
     'id': 'summarize_pr_triage_department', 'when': None},
]


def test_node_identity():
    assert _NODE_ID and _ATOM


def test_conduction_is_declared():
    assert _CONDUCTION == ['list_pr_sieve']


def test_required_when_fields_are_listed():
    assert _REQUIRED_WHEN_FIELDS == ['route']


def test_model_status_for_this_node():
    from support.graph_model import run_model
    assert run_model(_EFFECTORS, {})[_NODE_ID] in {'succeeded', 'skipped'}
