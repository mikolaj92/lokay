"""summarize_pr_triage_department in pr_triage_department: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'pr_triage_department'
_NODE_ID = 'summarize_pr_triage_department'
_ATOM = 'summarize_pr_triage_department'
_CONDUCTION = ['select_pr_sieve', 'run_pr_sieve', 'select_pr_triage_verdict']
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'list_pr_sieve', 'when': None},
 {'conduction': ['list_pr_sieve'], 'id': 'select_pr_sieve', 'when': None},
 {'conduction': ['select_pr_sieve'],
  'id': 'run_pr_sieve',
  'when': {'equals': 'pr', 'path': 'route', 'upstream': 'select_pr_sieve'}},
 {'conduction': ['select_pr_sieve', 'run_pr_sieve'], 'id': 'select_pr_triage_verdict', 'when': None},
 {'conduction': ['select_pr_sieve', 'run_pr_sieve', 'select_pr_triage_verdict'],
  'id': 'summarize_pr_triage_department',
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

