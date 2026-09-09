"""build_factory_begin_state in factory_begin: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'factory_begin'
_NODE_ID = 'build_factory_begin_state'
_ATOM = 'build_factory_begin_state'
_CONDUCTION = ['load_factory_config', 'select_factory_scope', 'read_factory_stuck', 'create_factory_pass_dir']
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'probe_factory_host', 'when': None},
 {'conduction': ['probe_factory_host'], 'id': 'load_factory_config', 'when': None},
 {'conduction': ['load_factory_config'], 'id': 'select_factory_scope', 'when': None},
 {'conduction': ['load_factory_config'], 'id': 'read_factory_stuck', 'when': None},
 {'conduction': ['load_factory_config', 'select_factory_scope'],
  'id': 'create_factory_pass_dir',
  'when': None},
 {'conduction': ['load_factory_config',
                 'select_factory_scope',
                 'read_factory_stuck',
                 'create_factory_pass_dir'],
  'id': 'build_factory_begin_state',
  'when': None},
 {'conduction': ['read_factory_stuck'], 'id': 'build_factory_working_state', 'when': None},
 {'conduction': ['build_factory_working_state'], 'id': 'seed_factory_occupancy', 'when': None},
 {'conduction': ['build_factory_begin_state', 'seed_factory_occupancy', 'read_factory_stuck'],
  'id': 'attach_factory_stuck',
  'when': None},
 {'conduction': ['create_factory_pass_dir', 'attach_factory_stuck'],
  'id': 'persist_factory_begin_state',
  'when': None},
 {'conduction': ['create_factory_pass_dir', 'attach_factory_stuck', 'persist_factory_begin_state'],
  'id': 'persist_factory_working_state',
  'when': None},
 {'conduction': ['probe_factory_host',
                 'read_factory_stuck',
                 'create_factory_pass_dir',
                 'attach_factory_stuck',
                 'persist_factory_working_state'],
  'id': 'persist_factory_tick',
  'when': None},
 {'conduction': ['persist_factory_tick'], 'id': 'classify_leftover_remaining', 'when': None},
 {'conduction': ['persist_factory_tick', 'classify_leftover_remaining'],
  'id': 'merge_leftover_remaining',
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

