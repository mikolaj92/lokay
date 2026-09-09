"""self_repair_commit in self_repair: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'self_repair'
_NODE_ID = 'self_repair_commit'
_ATOM = 'self_repair_commit'
_CONDUCTION = ['self_repair_prepare', 'self_repair_run_agent']
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'self_repair_prepare', 'when': None},
 {'conduction': ['self_repair_prepare'], 'id': 'self_repair_run_agent', 'when': None},
 {'conduction': ['self_repair_prepare', 'self_repair_run_agent'], 'id': 'self_repair_commit', 'when': None},
 {'conduction': ['self_repair_prepare', 'self_repair_commit'], 'id': 'self_repair_validate', 'when': None},
 {'conduction': ['self_repair_prepare', 'self_repair_validate', 'self_repair_commit'],
  'id': 'self_repair_push_main',
  'when': None},
 {'conduction': ['self_repair_push_main'], 'id': 'self_repair_activate', 'when': None},
 {'conduction': ['self_repair_activate'], 'id': 'self_repair_preflight', 'when': None},
 {'conduction': ['self_repair_preflight'], 'id': 'self_repair_close', 'when': None},
 {'conduction': ['self_repair_preflight',
                 'self_repair_push_main',
                 'self_repair_activate',
                 'self_repair_close'],
  'id': 'summarize_self_repair',
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

