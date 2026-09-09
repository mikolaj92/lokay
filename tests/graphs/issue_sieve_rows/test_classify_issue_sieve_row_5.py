"""classify_issue_sieve_row_5 in issue_sieve_rows: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'issue_sieve_rows'
_NODE_ID = 'classify_issue_sieve_row_5'
_ATOM = 'classify_issue_sieve_row_5'
_CONDUCTION = ['prepare_issue_sieve', 'select_issue_sieve_slot_5', 'run_issue_sieve_row_5', 'classify_issue_sieve_row_4']
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'prepare_issue_sieve', 'when': None},
 {'conduction': ['prepare_issue_sieve'], 'id': 'select_issue_sieve_slot_1', 'when': None},
 {'conduction': ['prepare_issue_sieve', 'select_issue_sieve_slot_1'],
  'id': 'run_issue_sieve_row_1',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_issue_sieve_slot_1'}},
 {'conduction': ['prepare_issue_sieve', 'select_issue_sieve_slot_1', 'run_issue_sieve_row_1'],
  'id': 'classify_issue_sieve_row_1',
  'when': None},
 {'conduction': ['prepare_issue_sieve', 'classify_issue_sieve_row_1'],
  'id': 'select_issue_sieve_slot_2',
  'when': None},
 {'conduction': ['prepare_issue_sieve', 'select_issue_sieve_slot_2', 'classify_issue_sieve_row_1'],
  'id': 'run_issue_sieve_row_2',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_issue_sieve_slot_2'}},
 {'conduction': ['prepare_issue_sieve',
                 'select_issue_sieve_slot_2',
                 'run_issue_sieve_row_2',
                 'classify_issue_sieve_row_1'],
  'id': 'classify_issue_sieve_row_2',
  'when': None},
 {'conduction': ['prepare_issue_sieve', 'classify_issue_sieve_row_2'],
  'id': 'select_issue_sieve_slot_3',
  'when': None},
 {'conduction': ['prepare_issue_sieve', 'select_issue_sieve_slot_3', 'classify_issue_sieve_row_2'],
  'id': 'run_issue_sieve_row_3',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_issue_sieve_slot_3'}},
 {'conduction': ['prepare_issue_sieve',
                 'select_issue_sieve_slot_3',
                 'run_issue_sieve_row_3',
                 'classify_issue_sieve_row_2'],
  'id': 'classify_issue_sieve_row_3',
  'when': None},
 {'conduction': ['prepare_issue_sieve', 'classify_issue_sieve_row_3'],
  'id': 'select_issue_sieve_slot_4',
  'when': None},
 {'conduction': ['prepare_issue_sieve', 'select_issue_sieve_slot_4', 'classify_issue_sieve_row_3'],
  'id': 'run_issue_sieve_row_4',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_issue_sieve_slot_4'}},
 {'conduction': ['prepare_issue_sieve',
                 'select_issue_sieve_slot_4',
                 'run_issue_sieve_row_4',
                 'classify_issue_sieve_row_3'],
  'id': 'classify_issue_sieve_row_4',
  'when': None},
 {'conduction': ['prepare_issue_sieve', 'classify_issue_sieve_row_4'],
  'id': 'select_issue_sieve_slot_5',
  'when': None},
 {'conduction': ['prepare_issue_sieve', 'select_issue_sieve_slot_5', 'classify_issue_sieve_row_4'],
  'id': 'run_issue_sieve_row_5',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_issue_sieve_slot_5'}},
 {'conduction': ['prepare_issue_sieve',
                 'select_issue_sieve_slot_5',
                 'run_issue_sieve_row_5',
                 'classify_issue_sieve_row_4'],
  'id': 'classify_issue_sieve_row_5',
  'when': None},
 {'conduction': ['prepare_issue_sieve',
                 'classify_issue_sieve_row_1',
                 'classify_issue_sieve_row_2',
                 'classify_issue_sieve_row_3',
                 'classify_issue_sieve_row_4',
                 'classify_issue_sieve_row_5'],
  'id': 'select_issue_sieve_result',
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

