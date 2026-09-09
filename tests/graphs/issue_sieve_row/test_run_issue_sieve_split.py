"""run_issue_sieve_split in issue_sieve_row: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'issue_sieve_row'
_NODE_ID = 'run_issue_sieve_split'
_ATOM = 'run_issue_sieve_split'
_CONDUCTION = ['select_issue_sieve']
_WHEN = {'equals': 'split', 'path': 'route', 'upstream': 'select_issue_sieve'}
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'select_next_issue', 'when': None},
 {'conduction': ['select_next_issue'],
  'id': 'issues_run_triage',
  'when': {'equals': 'issue', 'path': 'route', 'upstream': 'select_next_issue'}},
 {'conduction': ['select_next_issue', 'issues_run_triage'], 'id': 'select_issue_sieve', 'when': None},
 {'conduction': ['select_issue_sieve'],
  'id': 'run_issue_sieve_split',
  'when': {'equals': 'split', 'path': 'route', 'upstream': 'select_issue_sieve'}},
 {'conduction': ['select_next_issue', 'issues_run_triage', 'select_issue_sieve', 'run_issue_sieve_split'],
  'id': 'summarize_issue_sieve_row',
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

