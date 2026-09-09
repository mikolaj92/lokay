"""run_executor_rows in executor_department: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'executor_department'
_NODE_ID = 'run_executor_rows'
_ATOM = 'run_executor_rows'
_CONDUCTION = ['list_open_issues']
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'list_open_issues', 'when': None},
 {'conduction': ['list_open_issues'], 'id': 'run_executor_rows', 'when': None},
 {'conduction': ['list_open_issues', 'run_executor_rows'],
  'id': 'summarize_executor_department',
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

