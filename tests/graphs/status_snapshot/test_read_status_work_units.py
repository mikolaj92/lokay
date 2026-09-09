"""read_status_work_units in status_snapshot: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'status_snapshot'
_NODE_ID = 'read_status_work_units'
_ATOM = 'read_status_work_units'
_CONDUCTION = ['read_status_config']
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'read_status_config', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'classify_status_readiness', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'read_status_clone_facts', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'read_status_lease', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'read_status_pass_receipt', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'read_status_work_units', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'read_status_repo_locks', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'describe_status_graphs', 'when': None},
 {'conduction': ['read_status_config'],
  'id': 'run_status_preflight',
  'when': {'equals': True, 'path': 'preflight_requested', 'upstream': 'read_status_config'}},
 {'conduction': ['read_status_config', 'run_status_preflight'],
  'id': 'record_status_preflight',
  'when': None},
 {'conduction': ['read_status_config',
                 'classify_status_readiness',
                 'read_status_clone_facts',
                 'read_status_lease',
                 'read_status_pass_receipt',
                 'read_status_work_units',
                 'read_status_repo_locks',
                 'describe_status_graphs',
                 'record_status_preflight'],
  'id': 'reduce_status_snapshot',
  'when': None},
 {'conduction': ['reduce_status_snapshot'], 'id': 'status_snapshot_terminal', 'when': None}]

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

