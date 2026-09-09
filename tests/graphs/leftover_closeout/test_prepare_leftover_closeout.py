"""prepare_leftover_closeout in leftover_closeout: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'leftover_closeout'
_NODE_ID = 'prepare_leftover_closeout'
_ATOM = 'prepare_leftover_closeout'
_CONDUCTION = []
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'prepare_leftover_closeout', 'when': None},
 {'conduction': ['prepare_leftover_closeout'], 'id': 'leftover_catalog', 'when': None},
 {'conduction': ['leftover_catalog'], 'id': 'update_leftover_stamp', 'when': None}]

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

