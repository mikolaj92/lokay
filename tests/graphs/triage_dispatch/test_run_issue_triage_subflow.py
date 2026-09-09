"""run_issue_triage_subflow in triage_dispatch: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'triage_dispatch'
_NODE_ID = 'run_issue_triage_subflow'
_ATOM = 'run_issue_triage_subflow'
_CONDUCTION = ['select_triage_gate']
_WHEN = {'equals': 'run', 'path': 'route', 'upstream': 'select_triage_gate'}
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'select_triage_target', 'when': None},
 {'conduction': ['select_triage_target'],
  'id': 'check_triage_stuck',
  'when': {'equals': 'target', 'path': 'route', 'upstream': 'select_triage_target'}},
 {'conduction': ['select_triage_target', 'check_triage_stuck'], 'id': 'select_triage_gate', 'when': None},
 {'conduction': ['select_triage_gate'],
  'id': 'run_issue_triage_subflow',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_triage_gate'}},
 {'conduction': ['select_triage_gate', 'run_issue_triage_subflow'], 'id': 'select_triage_run', 'when': None},
 {'conduction': ['select_triage_run'], 'id': 'record_triage_dispatch', 'when': None},
 {'conduction': ['record_triage_dispatch'], 'id': 'summarize_triage_dispatch', 'when': None}]

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

