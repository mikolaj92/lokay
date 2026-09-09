"""select_issue_do_row in executor_row: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'executor_row'
_NODE_ID = 'select_issue_do_row'
_ATOM = 'select_issue_do_row'
_CONDUCTION = ['select_next_issue']
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'select_next_issue', 'when': None},
 {'conduction': ['select_next_issue'], 'id': 'select_issue_do_row', 'when': None},
 {'conduction': ['select_issue_do_row'], 'id': 'select_issue_executor', 'when': None},
 {'conduction': ['select_issue_executor'],
  'id': 'issues_launch_pr',
  'when': {'equals': 'do', 'path': 'route', 'upstream': 'select_issue_executor'}},
 {'conduction': ['select_next_issue', 'select_issue_do_row', 'select_issue_executor', 'issues_launch_pr'],
  'id': 'summarize_executor_row',
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

