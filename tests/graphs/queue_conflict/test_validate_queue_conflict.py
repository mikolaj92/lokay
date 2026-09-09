"""validate_queue_conflict in queue_conflict: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'queue_conflict'
_NODE_ID = 'validate_queue_conflict'
_ATOM = 'validate_queue_conflict'
_CONDUCTION = ['queue_conflict_agent']
_WHEN = None
_REQUIRED_WHEN_FIELDS = ['route']
_EFFECTORS = [{'conduction': [], 'id': 'select_queue_conflict_candidate', 'when': None},
 {'conduction': ['select_queue_conflict_candidate'],
  'id': 'check_queue_covering_pr',
  'when': {'equals': 'candidate', 'path': 'route', 'upstream': 'select_queue_conflict_candidate'}},
 {'conduction': ['select_queue_conflict_candidate', 'check_queue_covering_pr'],
  'id': 'select_queue_conflict_gate',
  'when': None},
 {'conduction': ['select_queue_conflict_gate'],
  'id': 'queue_conflict_agent',
  'when': {'equals': 'agent', 'path': 'route', 'upstream': 'select_queue_conflict_gate'}},
 {'conduction': ['queue_conflict_agent'], 'id': 'validate_queue_conflict', 'when': None},
 {'conduction': ['validate_queue_conflict', 'select_queue_conflict_gate'],
  'id': 'queue_conflict_retry_agent',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_queue_conflict'}},
 {'conduction': ['queue_conflict_retry_agent'], 'id': 'validate_queue_conflict_retry', 'when': None},
 {'conduction': ['select_queue_conflict_candidate',
                 'select_queue_conflict_gate',
                 'validate_queue_conflict',
                 'validate_queue_conflict_retry'],
  'id': 'select_queue_conflict_outcome',
  'when': None},
 {'conduction': ['select_queue_conflict_outcome'],
  'id': 'remove_queue_ready_label',
  'when': {'equals': 'close', 'path': 'route', 'upstream': 'select_queue_conflict_outcome'}},
 {'conduction': ['select_queue_conflict_outcome', 'remove_queue_ready_label'],
  'id': 'select_queue_tracker',
  'when': None},
 {'conduction': ['select_queue_tracker'],
  'id': 'add_queue_tracker_label',
  'when': {'equals': 'tracker', 'path': 'route', 'upstream': 'select_queue_tracker'}},
 {'conduction': ['select_queue_conflict_outcome', 'remove_queue_ready_label', 'add_queue_tracker_label'],
  'id': 'record_queue_conflict',
  'when': None},
 {'conduction': ['record_queue_conflict'], 'id': 'advance_implementation_selection', 'when': None},
 {'conduction': ['select_queue_conflict_candidate',
                 'record_queue_conflict',
                 'advance_implementation_selection'],
  'id': 'summarize_queue_conflict',
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

