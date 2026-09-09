"""repair_agent in local_repair_execution: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'local_repair_execution'
_NODE_ID = 'repair_agent'
_ATOM = 'repair_agent'
_CONDUCTION = ['prepare_local_repair_request']
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'prepare_local_repair_request', 'when': None},
 {'conduction': ['prepare_local_repair_request'], 'id': 'repair_agent', 'when': None},
 {'conduction': ['repair_agent', 'prepare_local_repair_request'],
  'id': 'validate_repair_result',
  'when': None},
 {'conduction': ['prepare_local_repair_request', 'validate_repair_result'],
  'id': 'local_repair_retry_agent',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_repair_result'}},
 {'conduction': ['validate_repair_result', 'local_repair_retry_agent'],
  'id': 'validate_local_repair_retry',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_repair_result'}},
 {'conduction': ['validate_repair_result', 'validate_local_repair_retry'],
  'id': 'select_repair_result',
  'when': None},
 {'conduction': ['prepare_local_repair_request', 'select_repair_result'],
  'id': 'assert_repair_diff',
  'when': {'equals': 'repaired', 'path': 'route', 'upstream': 'select_repair_result'}},
 {'conduction': ['prepare_local_repair_request', 'select_repair_result', 'assert_repair_diff'],
  'id': 'commit_repair',
  'when': {'equals': 'repaired', 'path': 'route', 'upstream': 'select_repair_result'}},
 {'conduction': ['prepare_local_repair_request',
                 'commit_repair',
                 'repair_agent',
                 'local_repair_retry_agent',
                 'select_repair_result'],
  'id': 'test_local_recheck',
  'when': {'equals': 'repaired', 'path': 'route', 'upstream': 'select_repair_result'}},
 {'conduction': ['test_local_recheck', 'select_repair_result'],
  'id': 'select_local_test_recheck',
  'when': None},
 {'conduction': ['select_repair_result', 'select_local_test_recheck'],
  'id': 'local_repair_terminal',
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

