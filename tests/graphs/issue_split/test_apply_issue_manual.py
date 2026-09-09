"""apply_issue_manual in issue_split: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'issue_split'
_NODE_ID = 'apply_issue_manual'
_ATOM = 'apply_issue_manual'
_CONDUCTION = ['get_issue', 'plan_issue_split', 'select_park_stop']
_WHEN = {'equals': 'skip', 'path': 'route', 'upstream': 'select_park_stop'}
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'get_issue', 'when': None},
 {'conduction': ['get_issue'], 'id': 'plan_issue_split', 'when': None},
 {'conduction': ['get_issue', 'plan_issue_split'],
  'id': 'create_issue_split_child_1',
  'when': {'equals': 'present', 'path': 'child_1', 'upstream': 'plan_issue_split'}},
 {'conduction': ['get_issue', 'plan_issue_split', 'create_issue_split_child_1'],
  'id': 'create_issue_split_child_2',
  'when': {'equals': 'present', 'path': 'child_2', 'upstream': 'plan_issue_split'}},
 {'conduction': ['get_issue', 'plan_issue_split', 'create_issue_split_child_2'],
  'id': 'create_issue_split_child_3',
  'when': {'equals': 'present', 'path': 'child_3', 'upstream': 'plan_issue_split'}},
 {'conduction': ['get_issue', 'plan_issue_split', 'create_issue_split_child_3'],
  'id': 'create_issue_split_child_4',
  'when': {'equals': 'present', 'path': 'child_4', 'upstream': 'plan_issue_split'}},
 {'conduction': ['get_issue', 'plan_issue_split', 'create_issue_split_child_4'],
  'id': 'create_issue_split_child_5',
  'when': {'equals': 'present', 'path': 'child_5', 'upstream': 'plan_issue_split'}},
 {'conduction': ['get_issue',
                 'plan_issue_split',
                 'create_issue_split_child_1',
                 'create_issue_split_child_2',
                 'create_issue_split_child_3',
                 'create_issue_split_child_4',
                 'create_issue_split_child_5'],
  'id': 'mark_issue_tracker',
  'when': {'equals': 'children', 'path': 'route', 'upstream': 'plan_issue_split'}},
 {'conduction': ['get_issue',
                 'plan_issue_split',
                 'create_issue_split_child_1',
                 'create_issue_split_child_2',
                 'create_issue_split_child_3',
                 'create_issue_split_child_4',
                 'create_issue_split_child_5',
                 'mark_issue_tracker'],
  'id': 'comment_issue_tracker',
  'when': {'equals': 'children', 'path': 'route', 'upstream': 'plan_issue_split'}},
 {'conduction': ['get_issue', 'plan_issue_split', 'comment_issue_tracker'],
  'id': 'close_issue_tracker',
  'when': {'equals': 'children', 'path': 'route', 'upstream': 'plan_issue_split'}},
 {'conduction': ['plan_issue_split'],
  'id': 'select_park_stop',
  'when': {'equals': 'park', 'path': 'route', 'upstream': 'plan_issue_split'}},
 {'conduction': ['get_issue', 'plan_issue_split', 'select_park_stop'],
  'id': 'apply_issue_manual',
  'when': {'equals': 'skip', 'path': 'route', 'upstream': 'select_park_stop'}},
 {'conduction': ['plan_issue_split',
                 'comment_issue_tracker',
                 'close_issue_tracker',
                 'select_park_stop',
                 'apply_issue_manual'],
  'id': 'summarize_issue_split',
  'when': None}]

def test_node_identity():
    assert _NODE_ID
    assert _ATOM

def test_conduction_is_declared():
    assert isinstance(_CONDUCTION, list)

def test_when_is_declared():
    assert _WHEN["upstream"] in _CONDUCTION
    assert _WHEN["path"]
    assert "equals" in _WHEN

def test_required_when_fields_are_listed():
    assert all(isinstance(field, str) and field for field in _REQUIRED_WHEN_FIELDS)

def test_model_status_for_this_node():
    from support.graph_model import run_model
    status = run_model(_EFFECTORS, {})
    assert _NODE_ID in status
    assert status[_NODE_ID] in {"succeeded", "skipped"}

