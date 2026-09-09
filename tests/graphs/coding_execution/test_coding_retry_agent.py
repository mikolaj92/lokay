"""coding_retry_agent in coding_execution: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'coding_execution'
_NODE_ID = 'coding_retry_agent'
_ATOM = 'coding_retry_agent'
_CONDUCTION = ['prepare_coding_request', 'validate_coding_result']
_WHEN = {'equals': 'retry', 'path': 'route', 'upstream': 'validate_coding_result'}
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'prepare_coding_request', 'when': None},
 {'conduction': ['prepare_coding_request'], 'id': 'run_agent', 'when': None},
 {'conduction': ['run_agent'], 'id': 'validate_coding_result', 'when': None},
 {'conduction': ['prepare_coding_request', 'validate_coding_result'],
  'id': 'coding_retry_agent',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_coding_result'}},
 {'conduction': ['validate_coding_result', 'coding_retry_agent'],
  'id': 'validate_coding_retry',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_coding_result'}},
 {'conduction': ['validate_coding_result', 'validate_coding_retry'],
  'id': 'select_coding_result',
  'when': None},
 {'conduction': ['prepare_coding_request', 'select_coding_result'],
  'id': 'collect_coding_issue_snapshot',
  'when': {'equals': 'issue_snapshot', 'path': 'evidence_kind', 'upstream': 'select_coding_result'}},
 {'conduction': ['prepare_coding_request', 'select_coding_result'],
  'id': 'collect_coding_repo_structure',
  'when': {'equals': 'repo_structure', 'path': 'evidence_kind', 'upstream': 'select_coding_result'}},
 {'conduction': ['prepare_coding_request', 'select_coding_result'],
  'id': 'collect_coding_test_contract',
  'when': {'equals': 'test_contract', 'path': 'evidence_kind', 'upstream': 'select_coding_result'}},
 {'conduction': ['prepare_coding_request', 'select_coding_result'],
  'id': 'collect_coding_localized_diff',
  'when': {'equals': 'localized_diff', 'path': 'evidence_kind', 'upstream': 'select_coding_result'}},
 {'conduction': ['prepare_coding_request',
                 'select_coding_result',
                 'collect_coding_issue_snapshot',
                 'collect_coding_repo_structure',
                 'collect_coding_test_contract',
                 'collect_coding_localized_diff'],
  'id': 'evidence_coding_agent',
  'when': {'equals': 'evidence', 'path': 'route', 'upstream': 'select_coding_result'}},
 {'conduction': ['select_coding_result', 'evidence_coding_agent'],
  'id': 'validate_evidence_coding',
  'when': {'equals': 'evidence', 'path': 'route', 'upstream': 'select_coding_result'}},
 {'conduction': ['select_coding_result', 'validate_evidence_coding'],
  'id': 'select_evidence_coding',
  'when': None},
 {'conduction': ['select_coding_result', 'select_evidence_coding'],
  'id': 'finalize_coding_result',
  'when': None},
 {'conduction': ['finalize_coding_result'],
  'id': 'coding_fail_closed',
  'when': {'equals': 'fail_closed', 'path': 'route', 'upstream': 'finalize_coding_result'}},
 {'conduction': ['finalize_coding_result', 'coding_fail_closed'],
  'id': 'coding_execution_terminal',
  'when': None}]

def test_node_identity():
    assert _NODE_ID
    assert _ATOM

def test_conduction_is_declared():
    assert isinstance(_CONDUCTION, list)

def test_when_is_declared():
    assert _WHEN["upstream"] in _CONDUCTION
    assert _WHEN["path"]
    assert "equals" in _WHEN

def test_required_when_fields_are_listed():
    assert all(isinstance(field, str) and field for field in _REQUIRED_WHEN_FIELDS)

def test_model_status_for_this_node():
    from support.graph_model import run_model
    status = run_model(_EFFECTORS, {})
    assert _NODE_ID in status
    assert status[_NODE_ID] in {"succeeded", "skipped"}

