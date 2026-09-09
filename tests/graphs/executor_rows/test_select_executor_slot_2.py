"""select_executor_slot_2 in executor_rows: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'executor_rows'
_NODE_ID = 'select_executor_slot_2'
_ATOM = 'select_executor_slot_2'
_CONDUCTION = ['prepare_executor_rows', 'classify_executor_row_1']
_WHEN = None
_REQUIRED_WHEN_FIELDS = ['route']
_EFFECTORS = [{'conduction': [], 'id': 'prepare_executor_rows', 'when': None},
 {'conduction': ['prepare_executor_rows'], 'id': 'select_executor_slot_1', 'when': None},
 {'conduction': ['prepare_executor_rows', 'select_executor_slot_1'],
  'id': 'run_executor_row_1',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_executor_slot_1'}},
 {'conduction': ['prepare_executor_rows', 'select_executor_slot_1', 'run_executor_row_1'],
  'id': 'classify_executor_row_1',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'classify_executor_row_1'],
  'id': 'select_executor_slot_2',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'select_executor_slot_2', 'classify_executor_row_1'],
  'id': 'run_executor_row_2',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_executor_slot_2'}},
 {'conduction': ['prepare_executor_rows',
                 'select_executor_slot_2',
                 'run_executor_row_2',
                 'classify_executor_row_1'],
  'id': 'classify_executor_row_2',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'classify_executor_row_2'],
  'id': 'select_executor_slot_3',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'select_executor_slot_3', 'classify_executor_row_2'],
  'id': 'run_executor_row_3',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_executor_slot_3'}},
 {'conduction': ['prepare_executor_rows',
                 'select_executor_slot_3',
                 'run_executor_row_3',
                 'classify_executor_row_2'],
  'id': 'classify_executor_row_3',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'classify_executor_row_3'],
  'id': 'select_executor_slot_4',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'select_executor_slot_4', 'classify_executor_row_3'],
  'id': 'run_executor_row_4',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_executor_slot_4'}},
 {'conduction': ['prepare_executor_rows',
                 'select_executor_slot_4',
                 'run_executor_row_4',
                 'classify_executor_row_3'],
  'id': 'classify_executor_row_4',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'classify_executor_row_4'],
  'id': 'select_executor_slot_5',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'select_executor_slot_5', 'classify_executor_row_4'],
  'id': 'run_executor_row_5',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_executor_slot_5'}},
 {'conduction': ['prepare_executor_rows',
                 'select_executor_slot_5',
                 'run_executor_row_5',
                 'classify_executor_row_4'],
  'id': 'classify_executor_row_5',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'classify_executor_row_5'],
  'id': 'select_executor_slot_6',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'select_executor_slot_6', 'classify_executor_row_5'],
  'id': 'run_executor_row_6',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_executor_slot_6'}},
 {'conduction': ['prepare_executor_rows',
                 'select_executor_slot_6',
                 'run_executor_row_6',
                 'classify_executor_row_5'],
  'id': 'classify_executor_row_6',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'classify_executor_row_6'],
  'id': 'select_executor_slot_7',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'select_executor_slot_7', 'classify_executor_row_6'],
  'id': 'run_executor_row_7',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_executor_slot_7'}},
 {'conduction': ['prepare_executor_rows',
                 'select_executor_slot_7',
                 'run_executor_row_7',
                 'classify_executor_row_6'],
  'id': 'classify_executor_row_7',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'classify_executor_row_7'],
  'id': 'select_executor_slot_8',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'select_executor_slot_8', 'classify_executor_row_7'],
  'id': 'run_executor_row_8',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_executor_slot_8'}},
 {'conduction': ['prepare_executor_rows',
                 'select_executor_slot_8',
                 'run_executor_row_8',
                 'classify_executor_row_7'],
  'id': 'classify_executor_row_8',
  'when': None},
 {'conduction': ['prepare_executor_rows',
                 'classify_executor_row_1',
                 'classify_executor_row_2',
                 'classify_executor_row_3',
                 'classify_executor_row_4',
                 'classify_executor_row_5',
                 'classify_executor_row_6',
                 'classify_executor_row_7',
                 'classify_executor_row_8'],
  'id': 'select_executor_result',
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

def test_required_when_fields_live_on_domain_output():
    values = {"ok": True, "atom": _ATOM}
    for field in _REQUIRED_WHEN_FIELDS:
        if "." in field:
            current = values
            parts = field.split(".")
            for part in parts[:-1]:
                current = current.setdefault(part, {})
            current.setdefault(parts[-1], "value")
        else:
            values.setdefault(field, "value")
    from support.graph_model import lookup_path
    for field in _REQUIRED_WHEN_FIELDS:
        found, _ = lookup_path(values, field)
        assert found, field

