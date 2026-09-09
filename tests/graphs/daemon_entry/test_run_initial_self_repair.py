"""run_initial_self_repair in daemon_entry: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'daemon_entry'
_NODE_ID = 'run_initial_self_repair'
_ATOM = 'run_initial_self_repair'
_CONDUCTION = ['classify_daemon_preflight']
_WHEN = {'equals': 'repair', 'path': 'route', 'upstream': 'classify_daemon_preflight'}
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'classify_daemon_preflight', 'when': None},
 {'conduction': ['classify_daemon_preflight'],
  'id': 'run_daemon_product_cycle',
  'when': {'equals': 'product', 'path': 'route', 'upstream': 'classify_daemon_preflight'}},
 {'conduction': ['classify_daemon_preflight'],
  'id': 'run_initial_self_repair',
  'when': {'equals': 'repair', 'path': 'route', 'upstream': 'classify_daemon_preflight'}},
 {'conduction': ['classify_daemon_preflight', 'run_daemon_product_cycle', 'run_initial_self_repair'],
  'id': 'daemon_entry_terminal',
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

