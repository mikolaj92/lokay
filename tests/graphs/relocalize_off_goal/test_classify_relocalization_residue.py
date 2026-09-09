"""classify_relocalization_residue in relocalize_off_goal: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'relocalize_off_goal'
_NODE_ID = 'classify_relocalization_residue'
_ATOM = 'classify_relocalization_residue'
_CONDUCTION = ['read_relocalization_changed_paths', 'read_relocalization_issue_paths']
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'inspect_relocalization_evidence', 'when': None},
 {'conduction': ['inspect_relocalization_evidence'], 'id': 'read_relocalization_changed_paths', 'when': None},
 {'conduction': [], 'id': 'read_relocalization_issue_paths', 'when': None},
 {'conduction': ['read_relocalization_changed_paths', 'read_relocalization_issue_paths'],
  'id': 'classify_relocalization_residue',
  'when': None},
 {'conduction': ['classify_relocalization_residue'], 'id': 'authorize_relocalization_restore', 'when': None},
 {'conduction': ['inspect_relocalization_evidence',
                 'read_relocalization_changed_paths',
                 'authorize_relocalization_restore'],
  'id': 'restore_relocalization_residue',
  'when': {'equals': 'restore', 'path': 'route', 'upstream': 'authorize_relocalization_restore'}},
 {'conduction': ['classify_relocalization_residue',
                 'authorize_relocalization_restore',
                 'restore_relocalization_residue'],
  'id': 'record_relocalization_restore',
  'when': None},
 {'conduction': ['inspect_relocalization_evidence',
                 'read_relocalization_changed_paths',
                 'record_relocalization_restore'],
  'id': 'classify_relocalization_off_goal',
  'when': None},
 {'conduction': ['inspect_relocalization_evidence', 'classify_relocalization_off_goal'],
  'id': 'build_relocalization_agent_request',
  'when': None},
 {'conduction': ['inspect_relocalization_evidence', 'build_relocalization_agent_request'],
  'id': 'run_relocalization_agent',
  'when': {'equals': 'agent', 'path': 'route', 'upstream': 'build_relocalization_agent_request'}},
 {'conduction': ['run_relocalization_agent'], 'id': 'validate_relocalization_agent_json', 'when': None},
 {'conduction': ['validate_relocalization_agent_json'], 'id': 'build_relocalization_retry', 'when': None},
 {'conduction': ['inspect_relocalization_evidence',
                 'build_relocalization_agent_request',
                 'build_relocalization_retry'],
  'id': 'retry_relocalization_agent',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'build_relocalization_retry'}},
 {'conduction': ['retry_relocalization_agent'], 'id': 'validate_relocalization_retry_json', 'when': None},
 {'conduction': ['run_relocalization_agent',
                 'validate_relocalization_agent_json',
                 'retry_relocalization_agent',
                 'validate_relocalization_retry_json'],
  'id': 'select_relocalization_validation',
  'when': None},
 {'conduction': ['classify_relocalization_off_goal', 'select_relocalization_validation'],
  'id': 'validate_relocalization_approval',
  'when': None},
 {'conduction': ['inspect_relocalization_evidence',
                 'classify_relocalization_off_goal',
                 'validate_relocalization_approval'],
  'id': 'write_relocalization_evidence',
  'when': {'equals': 'write', 'path': 'route', 'upstream': 'validate_relocalization_approval'}},
 {'conduction': ['inspect_relocalization_evidence',
                 'read_relocalization_changed_paths',
                 'classify_relocalization_off_goal',
                 'validate_relocalization_approval',
                 'write_relocalization_evidence'],
  'id': 'relocalization_terminal',
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

