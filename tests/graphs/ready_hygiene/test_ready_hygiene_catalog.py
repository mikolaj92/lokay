"""ready_hygiene_catalog in ready_hygiene: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'ready_hygiene'
_NODE_ID = 'ready_hygiene_catalog'
_ATOM = 'ready_hygiene_catalog'
_CONDUCTION = ['prepare_ready_hygiene']
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'prepare_ready_hygiene', 'when': None},
 {'conduction': ['prepare_ready_hygiene'], 'id': 'ready_hygiene_catalog', 'when': None},
 {'conduction': ['ready_hygiene_catalog'], 'id': 'update_ready_hygiene_stamp', 'when': None}]

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

