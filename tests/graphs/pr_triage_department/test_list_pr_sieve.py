"""list_pr_sieve in pr_triage_department: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'pr_triage_department'
_NODE_ID = 'list_pr_sieve'
_ATOM = 'list_pr_sieve'
_CONDUCTION = []
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'list_pr_sieve', 'when': None},
 {'conduction': ['list_pr_sieve'], 'id': 'select_pr_sieve', 'when': None},
 {'conduction': ['select_pr_sieve'], 'id': 'observe_delivery_replay', 'when': None},
 {'conduction': ['select_pr_sieve', 'observe_delivery_replay'],
  'id': 'close_delivery_replay',
  'when': {'equals': 'close', 'path': 'route', 'upstream': 'observe_delivery_replay'}},
 {'conduction': ['select_pr_sieve', 'observe_delivery_replay', 'close_delivery_replay'],
  'id': 'publish_delivery_replay',
  'when': {'equals': 'publish', 'path': 'route', 'upstream': 'close_delivery_replay'}},
 {'conduction': ['select_pr_sieve', 'observe_delivery_replay'],
  'id': 'reconcile_pr_repair_push',
  'when': None},
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
                 'recover_repair_unavailable',
                 'observe_delivery_replay',
                 'close_delivery_replay',
                 'publish_delivery_replay'],
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
                 'recover_repair_unavailable',
                 'observe_delivery_replay',
                 'close_delivery_replay',
                 'publish_delivery_replay'],
  'id': 'summarize_pr_triage_department',
  'when': None}]

def test_node_identity():
    assert _NODE_ID
    assert _ATOM

def test_conduction_is_declared():
    assert isinstance(_CONDUCTION, list)

def test_required_when_fields_are_listed():
    assert all(isinstance(field, str) and field for field in _REQUIRED_WHEN_FIELDS)

def test_model_status_for_this_node():
    from support.graph_model import run_model
    status = run_model(_EFFECTORS, {})
    assert _NODE_ID in status
    assert status[_NODE_ID] in {"succeeded", "skipped"}

