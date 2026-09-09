"""record_authored_self_repair in self_repair_entry: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'self_repair_entry'
_NODE_ID = 'record_authored_self_repair'
_ATOM = 'record_authored_self_repair'
_CONDUCTION = ['classify_self_repair_entry', 'run_authored_self_repair']
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'prepare_self_repair_entry', 'when': None},
 {'conduction': ['prepare_self_repair_entry'], 'id': 'classify_self_repair_entry', 'when': None},
 {'conduction': ['prepare_self_repair_entry', 'classify_self_repair_entry'],
  'id': 'record_self_repair_entry_start',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'classify_self_repair_entry'}},
 {'conduction': ['prepare_self_repair_entry', 'classify_self_repair_entry', 'record_self_repair_entry_start'],
  'id': 'run_authored_self_repair',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'classify_self_repair_entry'}},
 {'conduction': ['classify_self_repair_entry', 'run_authored_self_repair'],
  'id': 'record_authored_self_repair',
  'when': None},
 {'conduction': ['record_authored_self_repair'], 'id': 'classify_self_repair_entry_outcome', 'when': None},
 {'conduction': ['prepare_self_repair_entry', 'classify_self_repair_entry_outcome'],
  'id': 'write_self_repair_restart_marker',
  'when': {'equals': 'restart', 'path': 'route', 'upstream': 'classify_self_repair_entry_outcome'}},
 {'conduction': ['prepare_self_repair_entry',
                 'classify_self_repair_entry',
                 'classify_self_repair_entry_outcome',
                 'write_self_repair_restart_marker'],
  'id': 'select_self_repair_entry_result',
  'when': None},
 {'conduction': ['prepare_self_repair_entry', 'select_self_repair_entry_result'],
  'id': 'record_self_repair_entry_success',
  'when': {'equals': 'success', 'path': 'route', 'upstream': 'select_self_repair_entry_result'}},
 {'conduction': ['prepare_self_repair_entry', 'select_self_repair_entry_result'],
  'id': 'record_self_repair_entry_failure',
  'when': {'equals': 'failure', 'path': 'route', 'upstream': 'select_self_repair_entry_result'}},
 {'conduction': ['select_self_repair_entry_result',
                 'record_self_repair_entry_success',
                 'record_self_repair_entry_failure'],
  'id': 'self_repair_entry_terminal',
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

