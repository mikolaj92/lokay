"""close_existing_delivery in issue_to_pr: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'issue_to_pr'
_NODE_ID = 'close_existing_delivery'
_ATOM = 'close_existing_delivery'
_CONDUCTION = ['get_issue', 'resolve_existing_delivery']
_WHEN = {'equals': 'closeout', 'path': 'route', 'upstream': 'resolve_existing_delivery'}
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'get_issue', 'when': None},
 {'conduction': ['get_issue'], 'id': 'resolve_implementation_issue', 'when': None},
 {'conduction': ['get_issue', 'resolve_implementation_issue'],
  'id': 'collect_existing_delivery_pr',
  'when': None},
 {'conduction': ['get_issue', 'resolve_implementation_issue'], 'id': 'collect_resumed_source', 'when': None},
 {'conduction': ['resolve_implementation_issue', 'collect_existing_delivery_pr', 'collect_resumed_source'],
  'id': 'resolve_existing_delivery',
  'when': None},
 {'conduction': ['get_issue', 'resolve_existing_delivery'],
  'id': 'issue_to_pr_subflow',
  'when': {'equals': 'deliver', 'path': 'route', 'upstream': 'resolve_existing_delivery'}},
 {'conduction': ['get_issue', 'resolve_existing_delivery'],
  'id': 'close_existing_delivery',
  'when': {'equals': 'closeout', 'path': 'route', 'upstream': 'resolve_existing_delivery'}},
 {'conduction': ['resolve_existing_delivery'],
  'id': 'issue_to_pr_no_effect',
  'when': {'equals': 'no_effect', 'path': 'route', 'upstream': 'resolve_existing_delivery'}},
 {'conduction': ['resolve_existing_delivery',
                 'issue_to_pr_subflow',
                 'close_existing_delivery',
                 'issue_to_pr_no_effect'],
  'id': 'summarize_issue_to_pr',
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

