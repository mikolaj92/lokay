"""test_local in pr_triage: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'pr_triage'
_NODE_ID = 'test_local'
_ATOM = 'test_local'
_CONDUCTION = ['publish_pr_review', 'worktree_add']
_WHEN = {'equals': 'approve', 'path': 'decision.verdict', 'upstream': 'publish_pr_review'}
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'pr_checks', 'when': None},
 {'conduction': ['pr_checks'], 'id': 'classify_pr_triage_checks', 'when': None},
 {'conduction': ['pr_checks', 'classify_pr_triage_checks'],
  'id': 'collect_pr_review_evidence',
  'when': {'equals': 'review', 'path': 'route', 'upstream': 'classify_pr_triage_checks'}},
 {'conduction': ['classify_pr_triage_checks', 'collect_pr_review_evidence'],
  'id': 'resolve_sha_review',
  'when': None},
 {'conduction': ['classify_pr_triage_checks', 'collect_pr_review_evidence', 'resolve_sha_review'],
  'id': 'pr_review_agent',
  'when': {'equals': 'agent', 'path': 'route', 'upstream': 'resolve_sha_review'}},
 {'conduction': ['classify_pr_triage_checks', 'resolve_sha_review', 'pr_review_agent'],
  'id': 'validate_pr_review',
  'when': None},
 {'conduction': ['collect_pr_review_evidence', 'validate_pr_review'],
  'id': 'pr_review_retry_agent',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_pr_review'}},
 {'conduction': ['validate_pr_review', 'pr_review_retry_agent'],
  'id': 'validate_pr_review_retry',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_pr_review'}},
 {'conduction': ['classify_pr_triage_checks',
                 'resolve_sha_review',
                 'validate_pr_review',
                 'validate_pr_review_retry'],
  'id': 'select_pr_review',
  'when': None},
 {'conduction': ['classify_pr_triage_checks', 'collect_pr_review_evidence', 'select_pr_review'],
  'id': 'review_evidence_catalog',
  'when': {'equals': 'evidence', 'path': 'route', 'upstream': 'select_pr_review'}},
 {'conduction': ['collect_pr_review_evidence', 'select_pr_review', 'review_evidence_catalog'],
  'id': 'evidence_review_agent',
  'when': {'equals': 'agent', 'path': 'route', 'upstream': 'review_evidence_catalog'}},
 {'conduction': ['select_pr_review', 'review_evidence_catalog', 'evidence_review_agent'],
  'id': 'validate_evidence_review',
  'when': {'equals': 'agent', 'path': 'route', 'upstream': 'review_evidence_catalog'}},
 {'conduction': ['classify_pr_triage_checks', 'select_pr_review', 'validate_evidence_review'],
  'id': 'select_evidence_review',
  'when': {'equals': 'review', 'path': 'route', 'upstream': 'classify_pr_triage_checks'}},
 {'conduction': ['classify_pr_triage_checks', 'select_pr_review', 'select_evidence_review'],
  'id': 'finalize_pr_review',
  'when': {'equals': 'review', 'path': 'route', 'upstream': 'classify_pr_triage_checks'}},
 {'conduction': ['classify_pr_triage_checks', 'collect_pr_review_evidence', 'finalize_pr_review'],
  'id': 'publish_pr_review',
  'when': None},
 {'conduction': ['classify_pr_triage_checks', 'publish_pr_review'], 'id': 'review_repair_gate', 'when': None},
 {'conduction': ['publish_pr_review', 'review_repair_gate'],
  'id': 'review_repair_manual',
  'when': {'equals': 'fail_closed', 'path': 'route', 'upstream': 'review_repair_gate'}},
 {'conduction': ['publish_pr_review'],
  'id': 'review_manual',
  'when': {'equals': 'fail_closed', 'path': 'decision.verdict', 'upstream': 'publish_pr_review'}},
 {'conduction': ['pr_checks', 'publish_pr_review'],
  'id': 'worktree_add',
  'when': {'equals': 'approve', 'path': 'decision.verdict', 'upstream': 'publish_pr_review'}},
 {'conduction': ['publish_pr_review', 'worktree_add'],
  'id': 'test_local',
  'when': {'equals': 'approve', 'path': 'decision.verdict', 'upstream': 'publish_pr_review'}},
 {'conduction': ['classify_pr_triage_checks', 'review_repair_gate', 'test_local'],
  'id': 'select_pr_triage_outcome',
  'when': None},
 {'conduction': ['classify_pr_triage_checks', 'select_pr_triage_outcome', 'publish_pr_review'],
  'id': 'pr_repair_verdict',
  'when': {'equals': 'repair', 'path': 'route', 'upstream': 'select_pr_triage_outcome'}},
 {'conduction': ['pr_checks', 'publish_pr_review', 'test_local', 'select_pr_triage_outcome'],
  'id': 'pr_merge',
  'when': {'equals': 'merge', 'path': 'route', 'upstream': 'select_pr_triage_outcome'}},
 {'conduction': ['publish_pr_review', 'pr_merge', 'select_pr_triage_outcome'],
  'id': 'stage_clear',
  'when': {'equals': 'merge', 'path': 'route', 'upstream': 'select_pr_triage_outcome'}},
 {'conduction': ['publish_pr_review', 'pr_merge', 'stage_clear', 'select_pr_triage_outcome'],
  'id': 'close_issue',
  'when': {'equals': 'merge', 'path': 'route', 'upstream': 'select_pr_triage_outcome'}},
 {'conduction': ['pr_merge', 'close_issue', 'select_pr_triage_outcome'],
  'id': 'publish_delivery_receipt',
  'when': {'equals': 'merge', 'path': 'route', 'upstream': 'select_pr_triage_outcome'}},
 {'conduction': ['classify_pr_triage_checks',
                 'select_pr_triage_outcome',
                 'pr_repair_verdict',
                 'review_repair_manual',
                 'review_manual',
                 'pr_merge',
                 'close_issue',
                 'publish_delivery_receipt',
                 'publish_pr_review'],
  'id': 'summarize_pr_triage',
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

