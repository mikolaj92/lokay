"""summarize_closeout_pr in closeout_pr: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'closeout_pr'
_NODE_ID = 'summarize_closeout_pr'
_ATOM = 'summarize_closeout_pr'
_CONDUCTION = ['finalize_closeout_pr']
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'inspect_closeout_pr', 'when': None},
 {'conduction': ['inspect_closeout_pr'], 'id': 'read_closeout_issue', 'when': None},
 {'conduction': ['inspect_closeout_pr', 'read_closeout_issue'], 'id': 'classify_closeout_gate', 'when': None},
 {'conduction': ['classify_closeout_gate'],
  'id': 'park_closed_pr_issue',
  'when': {'equals': 'issue_closed', 'path': 'route', 'upstream': 'classify_closeout_gate'}},
 {'conduction': ['classify_closeout_gate'],
  'id': 'read_closeout_checks',
  'when': {'equals': 'checks', 'path': 'route', 'upstream': 'classify_closeout_gate'}},
 {'conduction': ['classify_closeout_gate', 'read_closeout_checks'],
  'id': 'route_closeout_checks',
  'when': None},
 {'conduction': ['classify_closeout_gate', 'route_closeout_checks'],
  'id': 'authorize_closeout_repair',
  'when': None},
 {'conduction': ['classify_closeout_gate', 'authorize_closeout_repair'],
  'id': 'run_closeout_repair',
  'when': {'equals': 'repair', 'path': 'route', 'upstream': 'authorize_closeout_repair'}},
 {'conduction': ['classify_closeout_gate', 'route_closeout_checks'],
  'id': 'run_closeout_triage',
  'when': {'equals': 'triage', 'path': 'route', 'upstream': 'route_closeout_checks'}},
 {'conduction': ['route_closeout_checks', 'run_closeout_triage'],
  'id': 'classify_closeout_triage',
  'when': None},
 {'conduction': ['classify_closeout_gate', 'classify_closeout_triage'],
  'id': 'authorize_closeout_review_repair',
  'when': None},
 {'conduction': ['classify_closeout_gate', 'authorize_closeout_review_repair'],
  'id': 'run_closeout_review_repair',
  'when': {'equals': 'repair', 'path': 'route', 'upstream': 'authorize_closeout_review_repair'}},
 {'conduction': ['classify_closeout_gate', 'classify_closeout_triage'],
  'id': 'park_delivered_pr_issue',
  'when': {'equals': 'merged', 'path': 'route', 'upstream': 'classify_closeout_triage'}},
 {'conduction': ['authorize_closeout_repair',
                 'run_closeout_repair',
                 'authorize_closeout_review_repair',
                 'run_closeout_review_repair'],
  'id': 'select_closeout_repair_result',
  'when': None},
 {'conduction': ['park_closed_pr_issue', 'park_delivered_pr_issue'],
  'id': 'select_closeout_park_result',
  'when': None},
 {'conduction': ['classify_closeout_gate',
                 'route_closeout_checks',
                 'classify_closeout_triage',
                 'select_closeout_repair_result',
                 'select_closeout_park_result'],
  'id': 'build_closeout_evidence',
  'when': None},
 {'conduction': ['classify_closeout_gate',
                 'route_closeout_checks',
                 'classify_closeout_triage',
                 'select_closeout_repair_result',
                 'build_closeout_evidence'],
  'id': 'finalize_closeout_pr',
  'when': None},
 {'conduction': ['finalize_closeout_pr'], 'id': 'summarize_closeout_pr', 'when': None}]

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

