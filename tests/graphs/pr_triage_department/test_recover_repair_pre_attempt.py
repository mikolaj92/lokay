"""run_pr_sieve in pr_triage_department: graph metadata."""
from __future__ import annotations

_PATH_ID = 'pr_triage_department'
_NODE_ID = 'recover_repair_pre_attempt'
_ATOM = 'recover_repair_pre_attempt'
_CONDUCTION = ['reconcile_pr_repair_push']
_WHEN = {'equals': 'pre_attempt', 'path': 'recovery_case', 'upstream': 'reconcile_pr_repair_push'}
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'list_pr_sieve', 'when': None},
 {'conduction': ['list_pr_sieve'], 'id': 'select_pr_sieve', 'when': None},
 {'conduction': ['select_pr_sieve'], 'id': 'reconcile_pr_repair_push', 'when': None},
 {'conduction': ['reconcile_pr_repair_push'],
  'id': 'recover_repair_pre_attempt',
  'when': {'equals': 'pre_attempt',
           'path': 'recovery_case',
           'upstream': 'reconcile_pr_repair_push'}},
 {'conduction': ['reconcile_pr_repair_push'],
  'id': 'recover_repair_remote_unchanged',
  'when': {'equals': 'remote_unchanged',
           'path': 'recovery_case',
           'upstream': 'reconcile_pr_repair_push'}},
 {'conduction': ['reconcile_pr_repair_push'],
  'id': 'recover_repair_confirmed_target',
  'when': {'equals': 'confirmed_target',
           'path': 'recovery_case',
           'upstream': 'reconcile_pr_repair_push'}},
 {'conduction': ['reconcile_pr_repair_push'],
  'id': 'recover_repair_closed_merged',
  'when': {'equals': 'closed_merged',
           'path': 'recovery_case',
           'upstream': 'reconcile_pr_repair_push'}},
 {'conduction': ['reconcile_pr_repair_push'],
  'id': 'recover_repair_unavailable',
  'when': {'equals': 'unavailable',
           'path': 'recovery_case',
           'upstream': 'reconcile_pr_repair_push'}},
 {'conduction': ['reconcile_pr_repair_push'],
  'id': 'run_pr_sieve',
  'when': {'equals': 'review', 'path': 'route', 'upstream': 'reconcile_pr_repair_push'}},
 {'conduction': ['select_pr_sieve',
                 'reconcile_pr_repair_push',
                 'run_pr_sieve',
                 'recover_repair_pre_attempt',
                 'recover_repair_remote_unchanged',
                 'recover_repair_confirmed_target',
                 'recover_repair_closed_merged',
                 'recover_repair_unavailable'],
  'id': 'select_pr_triage_verdict',
  'when': None},
 {'conduction': ['select_pr_sieve',
                 'reconcile_pr_repair_push',
                 'run_pr_sieve',
                 'select_pr_triage_verdict',
                 'recover_repair_pre_attempt',
                 'recover_repair_remote_unchanged',
                 'recover_repair_confirmed_target',
                 'recover_repair_closed_merged',
                 'recover_repair_unavailable'],
  'id': 'summarize_pr_triage_department',
  'when': None}]


def test_node_identity():
    assert _NODE_ID and _ATOM


def test_conduction_is_declared():
    assert _CONDUCTION == ['reconcile_pr_repair_push']


def test_when_is_declared():
    assert _WHEN['path'] == 'recovery_case'
    assert _WHEN['equals'] == _NODE_ID.removeprefix('recover_repair_')


def test_model_status_for_this_node():
    from support.graph_model import run_model
    assert run_model(_EFFECTORS, {})[_NODE_ID] in {'succeeded', 'skipped'}
