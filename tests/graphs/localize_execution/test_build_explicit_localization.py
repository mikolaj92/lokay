"""build_explicit_localization in localize_execution: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'localize_execution'
_NODE_ID = 'build_explicit_localization'
_ATOM = 'build_explicit_localization'
_CONDUCTION = ['prepare_localization_request', 'inspect_existing_localization', 'classify_localization_route']
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'prepare_localization_request', 'when': None},
 {'conduction': ['prepare_localization_request'], 'id': 'inspect_existing_localization', 'when': None},
 {'conduction': ['prepare_localization_request', 'inspect_existing_localization'],
  'id': 'classify_localization_route',
  'when': None},
 {'conduction': ['prepare_localization_request',
                 'inspect_existing_localization',
                 'classify_localization_route'],
  'id': 'build_explicit_localization',
  'when': None},
 {'conduction': ['prepare_localization_request'], 'id': 'build_deterministic_localization', 'when': None},
 {'conduction': ['prepare_localization_request',
                 'inspect_existing_localization',
                 'classify_localization_route'],
  'id': 'build_localization_agent_request',
  'when': None},
 {'conduction': ['prepare_localization_request', 'build_localization_agent_request'],
  'id': 'run_localization_agent',
  'when': {'equals': 'agent', 'path': 'route', 'upstream': 'build_localization_agent_request'}},
 {'conduction': ['run_localization_agent'], 'id': 'validate_localization_agent_json', 'when': None},
 {'conduction': ['validate_localization_agent_json'], 'id': 'build_localization_retry', 'when': None},
 {'conduction': ['prepare_localization_request',
                 'build_localization_agent_request',
                 'build_localization_retry'],
  'id': 'retry_localization_agent',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'build_localization_retry'}},
 {'conduction': ['retry_localization_agent'], 'id': 'validate_localization_retry_json', 'when': None},
 {'conduction': ['classify_localization_route',
                 'build_explicit_localization',
                 'build_deterministic_localization',
                 'run_localization_agent',
                 'validate_localization_agent_json',
                 'retry_localization_agent',
                 'validate_localization_retry_json'],
  'id': 'select_localization_candidate',
  'when': None},
 {'conduction': ['prepare_localization_request',
                 'inspect_existing_localization',
                 'build_localization_agent_request',
                 'select_localization_candidate'],
  'id': 'validate_localization_paths',
  'when': None},
 {'conduction': ['prepare_localization_request', 'validate_localization_paths'],
  'id': 'write_localization_evidence',
  'when': None},
 {'conduction': ['select_localization_candidate', 'write_localization_evidence'],
  'id': 'localization_terminal',
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

