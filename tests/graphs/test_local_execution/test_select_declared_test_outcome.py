"""select_declared_test_outcome in test_local_execution: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'test_local_execution'
_NODE_ID = 'select_declared_test_outcome'
_ATOM = 'select_declared_test_outcome'
_CONDUCTION = ['run_declared_tests']
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'inspect_test_declaration', 'when': None},
 {'conduction': ['inspect_test_declaration'], 'id': 'read_test_green_cache', 'when': None},
 {'conduction': ['inspect_test_declaration', 'read_test_green_cache'],
  'id': 'run_declared_tests',
  'when': {'equals': 'miss', 'path': 'route', 'upstream': 'read_test_green_cache'}},
 {'conduction': ['run_declared_tests'], 'id': 'select_declared_test_outcome', 'when': None},
 {'conduction': ['inspect_test_declaration', 'select_declared_test_outcome'],
  'id': 'derive_changed_test_scope',
  'when': None},
 {'conduction': ['inspect_test_declaration', 'derive_changed_test_scope'],
  'id': 'run_changed_scope_tests',
  'when': {'equals': 'scope', 'path': 'route', 'upstream': 'derive_changed_test_scope'}},
 {'conduction': ['run_declared_tests', 'run_changed_scope_tests'],
  'id': 'select_green_test_result',
  'when': None},
 {'conduction': ['inspect_test_declaration', 'read_test_green_cache', 'select_green_test_result'],
  'id': 'write_test_green_cache',
  'when': None},
 {'conduction': ['inspect_test_declaration',
                 'read_test_green_cache',
                 'run_declared_tests',
                 'run_changed_scope_tests',
                 'write_test_green_cache'],
  'id': 'classify_test_terminal',
  'when': None},
 {'conduction': ['inspect_test_declaration',
                 'read_test_green_cache',
                 'run_declared_tests',
                 'run_changed_scope_tests',
                 'write_test_green_cache',
                 'classify_test_terminal'],
  'id': 'build_test_terminal_inspection',
  'when': {'equals': 'inspection', 'path': 'kind', 'upstream': 'classify_test_terminal'}},
 {'conduction': ['inspect_test_declaration',
                 'read_test_green_cache',
                 'run_declared_tests',
                 'run_changed_scope_tests',
                 'write_test_green_cache',
                 'classify_test_terminal'],
  'id': 'build_test_terminal_cached',
  'when': {'equals': 'cached', 'path': 'kind', 'upstream': 'classify_test_terminal'}},
 {'conduction': ['inspect_test_declaration',
                 'read_test_green_cache',
                 'run_declared_tests',
                 'run_changed_scope_tests',
                 'write_test_green_cache',
                 'classify_test_terminal'],
  'id': 'build_test_terminal_green',
  'when': {'equals': 'green', 'path': 'kind', 'upstream': 'classify_test_terminal'}},
 {'conduction': ['inspect_test_declaration',
                 'read_test_green_cache',
                 'run_declared_tests',
                 'run_changed_scope_tests',
                 'write_test_green_cache',
                 'classify_test_terminal'],
  'id': 'build_test_terminal_red',
  'when': {'equals': 'red', 'path': 'kind', 'upstream': 'classify_test_terminal'}},
 {'conduction': ['build_test_terminal_inspection',
                 'build_test_terminal_cached',
                 'build_test_terminal_green',
                 'build_test_terminal_red'],
  'id': 'select_test_terminal',
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

