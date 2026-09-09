"""summarize_implementation_selection in select_implement: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'select_implement'
_NODE_ID = 'summarize_implementation_selection'
_ATOM = 'summarize_implementation_selection'
_CONDUCTION = ['persist_implementation_selection']
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'prepare_implementation_selection', 'when': None},
 {'conduction': ['prepare_implementation_selection'], 'id': 'implementation_selection_catalog', 'when': None},
 {'conduction': ['implementation_selection_catalog'], 'id': 'persist_implementation_selection', 'when': None},
 {'conduction': ['persist_implementation_selection'],
  'id': 'summarize_implementation_selection',
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

