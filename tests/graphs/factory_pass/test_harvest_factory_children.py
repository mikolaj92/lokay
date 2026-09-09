"""harvest_factory_children in factory_pass: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'factory_pass'
_NODE_ID = 'harvest_factory_children'
_ATOM = 'harvest_factory_children'
_CONDUCTION = []
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'harvest_factory_children', 'when': None},
 {'conduction': ['harvest_factory_children'], 'id': 'host_ff', 'when': None},
 {'conduction': ['host_ff'], 'id': 'factory_begin_host_gate', 'when': None},
 {'conduction': ['factory_begin_host_gate'],
  'id': 'factory_begin',
  'when': {'equals': 'begin', 'path': 'route', 'upstream': 'factory_begin_host_gate'}},
 {'conduction': ['factory_begin_host_gate', 'factory_begin'],
  'id': 'select_self_repair_department',
  'when': None},
 {'conduction': ['select_self_repair_department'],
  'id': 'run_self_repair_department',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_self_repair_department'}},
 {'conduction': ['factory_begin_host_gate', 'factory_begin', 'select_self_repair_department'],
  'id': 'select_issue_triage_department',
  'when': None},
 {'conduction': ['select_issue_triage_department', 'factory_begin'],
  'id': 'run_issue_triage_department',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_issue_triage_department'}},
 {'conduction': ['factory_begin_host_gate',
                 'factory_begin',
                 'select_issue_triage_department',
                 'run_issue_triage_department'],
  'id': 'select_executor_department',
  'when': None},
 {'conduction': ['select_executor_department',
                 'factory_begin',
                 'run_issue_triage_department',
                 'select_issue_triage_department'],
  'id': 'run_executor_department',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_executor_department'}},
 {'conduction': ['factory_begin_host_gate', 'factory_begin', 'select_executor_department'],
  'id': 'select_pr_triage_department',
  'when': None},
 {'conduction': ['select_pr_triage_department'],
  'id': 'run_pr_triage_department',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_pr_triage_department'}},
 {'conduction': ['factory_begin_host_gate',
                 'factory_begin',
                 'select_pr_triage_department',
                 'run_pr_triage_department'],
  'id': 'select_pr_repair_department',
  'when': None},
 {'conduction': ['select_pr_repair_department'],
  'id': 'run_pr_repair_department',
  'when': {'equals': 'repair', 'path': 'route', 'upstream': 'select_pr_repair_department'}},
 {'conduction': ['factory_begin_host_gate',
                 'factory_begin',
                 'select_self_repair_department',
                 'select_issue_triage_department',
                 'select_executor_department',
                 'select_pr_triage_department',
                 'select_pr_repair_department',
                 'run_self_repair_department',
                 'run_issue_triage_department',
                 'run_executor_department',
                 'run_pr_triage_department',
                 'run_pr_repair_department'],
  'id': 'record_pass',
  'when': None},
 {'conduction': ['record_pass'], 'id': 'factory_pass_terminal', 'when': None},
 {'conduction': ['factory_begin_host_gate', 'factory_begin'], 'id': 'reap_stale_worktrees', 'when': None}]

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

