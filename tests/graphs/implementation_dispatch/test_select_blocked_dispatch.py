"""select_blocked_dispatch in implementation_dispatch: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'implementation_dispatch'
_NODE_ID = 'select_blocked_dispatch'
_ATOM = 'select_blocked_dispatch'
_CONDUCTION = ['persist_blocked_dispatch', 'select_dispatch_outcome']
_WHEN = None
_REQUIRED_WHEN_FIELDS = ['route']
_EFFECTORS = [{'conduction': [], 'id': 'select_implementation_candidate', 'when': None},
 {'conduction': ['select_implementation_candidate'],
  'id': 'inspect_implementation_mutex',
  'when': {'equals': 'candidate', 'path': 'route', 'upstream': 'select_implementation_candidate'}},
 {'conduction': ['select_implementation_candidate', 'inspect_implementation_mutex'],
  'id': 'select_mutex_outcome',
  'when': None},
 {'conduction': ['select_mutex_outcome'],
  'id': 'keep_implementation_candidate',
  'when': {'equals': 'keep', 'path': 'route', 'upstream': 'select_mutex_outcome'}},
 {'conduction': ['select_mutex_outcome'],
  'id': 'verify_selected_issue_ready',
  'when': {'equals': 'free', 'path': 'route', 'upstream': 'select_mutex_outcome'}},
 {'conduction': ['select_mutex_outcome', 'verify_selected_issue_ready'],
  'id': 'select_ready_outcome',
  'when': None},
 {'conduction': ['select_ready_outcome'],
  'id': 'drop_stale_implementation_candidate',
  'when': {'equals': 'stale', 'path': 'route', 'upstream': 'select_ready_outcome'}},
 {'conduction': ['select_ready_outcome'],
  'id': 'launch_issue_to_pr',
  'when': {'equals': 'ready', 'path': 'route', 'upstream': 'select_ready_outcome'}},
 {'conduction': ['select_ready_outcome', 'launch_issue_to_pr'], 'id': 'select_launch_route', 'when': None},
 {'conduction': ['select_launch_route'],
  'id': 'record_dispatch_success',
  'when': {'equals': 'started', 'path': 'route', 'upstream': 'select_launch_route'}},
 {'conduction': ['select_launch_route'],
  'id': 'record_dispatch_failure',
  'when': {'equals': 'failed', 'path': 'route', 'upstream': 'select_launch_route'}},
 {'conduction': ['select_launch_route'],
  'id': 'keep_busy_launch',
  'when': {'equals': 'busy', 'path': 'route', 'upstream': 'select_launch_route'}},
 {'conduction': ['record_dispatch_success', 'record_dispatch_failure'],
  'id': 'select_dispatch_outcome',
  'when': None},
 {'conduction': ['select_dispatch_outcome'],
  'id': 'persist_dispatch_stuck',
  'when': {'equals': True, 'path': 'stuck_changed', 'upstream': 'select_dispatch_outcome'}},
 {'conduction': ['select_dispatch_outcome'],
  'id': 'label_blocked_dispatch',
  'when': {'equals': 'blocked', 'path': 'route', 'upstream': 'select_dispatch_outcome'}},
 {'conduction': ['label_blocked_dispatch'], 'id': 'persist_blocked_dispatch', 'when': None},
 {'conduction': ['persist_blocked_dispatch', 'select_dispatch_outcome'],
  'id': 'select_blocked_dispatch',
  'when': None},
 {'conduction': ['select_blocked_dispatch'],
  'id': 'park_plan_only_dispatch',
  'when': {'equals': 'park', 'path': 'route', 'upstream': 'select_blocked_dispatch'}},
 {'conduction': ['select_dispatch_outcome'],
  'id': 'write_dispatch_receipt',
  'when': {'equals': 'receipt', 'path': 'route', 'upstream': 'select_dispatch_outcome'}},
 {'conduction': ['select_implementation_candidate',
                 'inspect_implementation_mutex',
                 'select_mutex_outcome',
                 'keep_implementation_candidate',
                 'verify_selected_issue_ready',
                 'select_ready_outcome',
                 'drop_stale_implementation_candidate',
                 'launch_issue_to_pr',
                 'select_launch_route',
                 'keep_busy_launch',
                 'record_dispatch_success',
                 'record_dispatch_failure',
                 'select_dispatch_outcome',
                 'persist_dispatch_stuck',
                 'label_blocked_dispatch',
                 'persist_blocked_dispatch',
                 'select_blocked_dispatch',
                 'park_plan_only_dispatch',
                 'write_dispatch_receipt'],
  'id': 'summarize_implementation_dispatch',
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

