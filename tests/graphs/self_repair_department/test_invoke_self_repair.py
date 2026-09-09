"""invoke_self_repair in self_repair_department: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'self_repair_department'
_NODE_ID = 'invoke_self_repair'
_ATOM = 'invoke_self_repair'
_CONDUCTION = ['open_self_repair_incident']
_WHEN = {'equals': 'run', 'path': 'route', 'upstream': 'open_self_repair_incident'}
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'open_self_repair_incident', 'when': None},
 {'conduction': ['open_self_repair_incident'],
  'id': 'invoke_self_repair',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'open_self_repair_incident'}}]

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

