"""reconcile_pr_repair_push in pr_triage_department: branch metadata."""
from __future__ import annotations

_PATH_ID = 'pr_triage_department'
_NODE_ID = 'reconcile_pr_repair_push'
_ATOM = 'reconcile_pr_repair_push'
_CONDUCTION = ['select_pr_sieve', 'observe_delivery_replay']
_WHEN = None
_REQUIRED_WHEN_FIELDS = ['recovery_case', 'route']
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
    assert _NODE_ID and _ATOM


def test_conduction_is_declared():
    assert _CONDUCTION == ['select_pr_sieve', 'observe_delivery_replay']


def test_when_is_not_a_branch():
    assert _WHEN is None


def test_model_status_for_this_node():
    from support.graph_model import run_model
    assert run_model(_EFFECTORS, {})[_NODE_ID] == 'succeeded'


def test_native_reconciliation_runs_without_selected_pr(tmp_path):
    from support.graph_model import node_status_map
    from support.native_path import run_overridden_path

    result = run_overridden_path(
        tmp_path, _PATH_ID,
        {
            'list_pr_sieve': {'ok': True, 'prs': []},
            'reconcile_pr_repair_push': {'ok': True, 'route': 'no_pr', 'recovery_case': 'none'},
            'select_pr_sieve': {'ok': True, 'route': 'none', 'reason': 'no_open_pr'},
        },
        run_id='reconcile-empty-pr-list', max_ticks=40,
    )
    status = node_status_map(result)
    assert result.get('run_status') == 'completed'
    assert status['reconcile_pr_repair_push'] == 'succeeded'
    assert status['run_pr_sieve'] == 'skipped'
    assert 'run_pr_sieve' not in result.get('_ran', [])
