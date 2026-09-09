"""issue_evidence_agent in issue_triage: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'issue_triage'
_NODE_ID = 'issue_evidence_agent'
_ATOM = 'issue_evidence_agent'
_CONDUCTION = ['get_issue', 'map_repo', 'resolve_issue_hard_facts', 'verify_issue_evidence']
_WHEN = {'equals': 'agent', 'path': 'route', 'upstream': 'verify_issue_evidence'}
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'get_issue', 'when': None},
 {'conduction': ['get_issue'], 'id': 'resolve_issue_candidate', 'when': None},
 {'conduction': ['get_issue', 'resolve_issue_candidate'],
  'id': 'collect_issue_linked_prs',
  'when': {'equals': 'evaluate', 'path': 'route', 'upstream': 'resolve_issue_candidate'}},
 {'conduction': ['get_issue', 'resolve_issue_candidate', 'collect_issue_linked_prs'],
  'id': 'collect_issue_covering_prs',
  'when': {'equals': 'evaluate', 'path': 'route', 'upstream': 'resolve_issue_candidate'}},
 {'conduction': ['get_issue',
                 'resolve_issue_candidate',
                 'collect_issue_linked_prs',
                 'collect_issue_covering_prs'],
  'id': 'resolve_issue_hard_facts',
  'when': None},
 {'conduction': ['get_issue', 'resolve_issue_hard_facts'], 'id': 'map_repo', 'when': None},
 {'conduction': ['get_issue', 'resolve_issue_hard_facts', 'map_repo'],
  'id': 'issue_triage_agent',
  'when': {'equals': 'agent', 'path': 'route', 'upstream': 'resolve_issue_hard_facts'}},
 {'conduction': ['resolve_issue_hard_facts', 'issue_triage_agent'],
  'id': 'validate_issue_triage',
  'when': None},
 {'conduction': ['get_issue', 'resolve_issue_hard_facts', 'map_repo', 'validate_issue_triage'],
  'id': 'issue_triage_retry_agent',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_issue_triage'}},
 {'conduction': ['validate_issue_triage', 'issue_triage_retry_agent'],
  'id': 'validate_issue_triage_retry',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_issue_triage'}},
 {'conduction': ['resolve_issue_hard_facts', 'validate_issue_triage', 'validate_issue_triage_retry'],
  'id': 'select_issue_triage',
  'when': None},
 {'conduction': ['select_issue_triage'],
  'id': 'collect_issue_repo_shape',
  'when': {'equals': 'repo_shape', 'path': 'evidence_kind', 'upstream': 'select_issue_triage'}},
 {'conduction': ['get_issue', 'select_issue_triage'],
  'id': 'collect_issue_named_paths',
  'when': {'equals': 'named_paths', 'path': 'evidence_kind', 'upstream': 'select_issue_triage'}},
 {'conduction': ['select_issue_triage',
                 'collect_issue_linked_prs',
                 'collect_issue_covering_prs',
                 'collect_issue_repo_shape',
                 'collect_issue_named_paths'],
  'id': 'verify_issue_evidence',
  'when': None},
 {'conduction': ['get_issue', 'map_repo', 'resolve_issue_hard_facts', 'verify_issue_evidence'],
  'id': 'issue_evidence_agent',
  'when': {'equals': 'agent', 'path': 'route', 'upstream': 'verify_issue_evidence'}},
 {'conduction': ['verify_issue_evidence', 'issue_evidence_agent'],
  'id': 'validate_issue_evidence',
  'when': {'equals': 'agent', 'path': 'route', 'upstream': 'verify_issue_evidence'}},
 {'conduction': ['select_issue_triage', 'validate_issue_evidence'],
  'id': 'select_issue_evidence',
  'when': None},
 {'conduction': ['select_issue_triage', 'select_issue_evidence'],
  'id': 'finalize_issue_triage',
  'when': None},
 {'conduction': ['finalize_issue_triage'], 'id': 'select_triage_leaf', 'when': None},
 {'conduction': ['get_issue', 'finalize_issue_triage', 'select_triage_leaf'],
  'id': 'apply_issue_blocked',
  'when': {'equals': 'blocked', 'path': 'route', 'upstream': 'select_triage_leaf'}},
 {'conduction': ['get_issue', 'finalize_issue_triage', 'select_triage_leaf'],
  'id': 'apply_issue_mark',
  'when': {'equals': 'close', 'path': 'route', 'upstream': 'select_triage_leaf'}},
 {'conduction': ['get_issue', 'finalize_issue_triage', 'select_triage_leaf'],
  'id': 'apply_issue_ready',
  'when': {'equals': 'ready', 'path': 'route', 'upstream': 'select_triage_leaf'}},
 {'conduction': ['get_issue', 'finalize_issue_triage', 'select_triage_leaf'],
  'id': 'apply_issue_skip',
  'when': {'equals': 'skip', 'path': 'route', 'upstream': 'select_triage_leaf'}},
 {'conduction': ['finalize_issue_triage', 'select_triage_leaf'],
  'id': 'select_park_stop',
  'when': {'equals': 'park', 'path': 'route', 'upstream': 'select_triage_leaf'}},
 {'conduction': ['get_issue', 'finalize_issue_triage', 'select_triage_leaf', 'select_park_stop'],
  'id': 'apply_issue_manual',
  'when': {'equals': 'skip', 'path': 'route', 'upstream': 'select_park_stop'}},
 {'conduction': ['finalize_issue_triage',
                 'select_triage_leaf',
                 'select_park_stop',
                 'apply_issue_ready',
                 'apply_issue_skip',
                 'apply_issue_blocked',
                 'apply_issue_mark',
                 'apply_issue_manual'],
  'id': 'summarize_issue_triage',
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

