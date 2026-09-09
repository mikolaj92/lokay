"""assert_real_diff in pr_repair: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'pr_repair'
_NODE_ID = 'assert_real_diff'
_ATOM = 'assert_real_diff'
_CONDUCTION = ['worktree_add', 'finalize_repair_tests']
_WHEN = {'equals': 'publish', 'path': 'route', 'upstream': 'finalize_repair_tests'}
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'admit_pr_repair', 'when': None},
 {'conduction': [], 'id': 'pr_checks', 'when': None},
 {'conduction': ['pr_checks'], 'id': 'stage_repairing', 'when': None},
 {'conduction': ['pr_checks', 'stage_repairing'], 'id': 'worktree_add', 'when': None},
 {'conduction': ['pr_checks', 'worktree_add'],
  'id': 'map_repo',
  'when': {'equals': 'ready', 'path': 'route', 'upstream': 'worktree_add'}},
 {'conduction': ['pr_checks', 'worktree_add', 'map_repo'],
  'id': 'localize',
  'when': {'equals': 'ready', 'path': 'route', 'upstream': 'worktree_add'}},
 {'conduction': ['pr_checks', 'worktree_add', 'map_repo', 'localize'],
  'id': 'run_agent',
  'when': {'equals': 'ready', 'path': 'route', 'upstream': 'localize'}},
 {'conduction': ['worktree_add', 'run_agent'],
  'id': 'validate_initial_repair',
  'when': {'equals': 'ready', 'path': 'route', 'upstream': 'worktree_add'}},
 {'conduction': ['worktree_add', 'validate_initial_repair'],
  'id': 'pr_repair_retry_agent',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_initial_repair'}},
 {'conduction': ['validate_initial_repair', 'pr_repair_retry_agent'],
  'id': 'validate_repair_retry',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_initial_repair'}},
 {'conduction': ['worktree_add', 'validate_initial_repair', 'validate_repair_retry'],
  'id': 'select_initial_repair',
  'when': {'equals': 'ready', 'path': 'route', 'upstream': 'worktree_add'}},
 {'conduction': ['worktree_add', 'select_initial_repair'],
  'id': 'collect_repair_pr_metadata',
  'when': {'equals': 'pr_metadata', 'path': 'evidence_kind', 'upstream': 'select_initial_repair'}},
 {'conduction': ['worktree_add', 'select_initial_repair'],
  'id': 'collect_repair_changed_files',
  'when': {'equals': 'changed_files', 'path': 'evidence_kind', 'upstream': 'select_initial_repair'}},
 {'conduction': ['worktree_add', 'select_initial_repair'],
  'id': 'collect_repair_test_contract',
  'when': {'equals': 'test_contract', 'path': 'evidence_kind', 'upstream': 'select_initial_repair'}},
 {'conduction': ['worktree_add', 'select_initial_repair'],
  'id': 'collect_repair_review_findings',
  'when': {'equals': 'review_findings', 'path': 'evidence_kind', 'upstream': 'select_initial_repair'}},
 {'conduction': ['worktree_add',
                 'select_initial_repair',
                 'collect_repair_pr_metadata',
                 'collect_repair_changed_files',
                 'collect_repair_test_contract',
                 'collect_repair_review_findings'],
  'id': 'evidence_repair_agent',
  'when': {'equals': 'evidence', 'path': 'route', 'upstream': 'select_initial_repair'}},
 {'conduction': ['select_initial_repair', 'evidence_repair_agent'],
  'id': 'validate_evidence_repair',
  'when': {'equals': 'evidence', 'path': 'route', 'upstream': 'select_initial_repair'}},
 {'conduction': ['select_initial_repair', 'validate_evidence_repair'],
  'id': 'select_evidence_repair',
  'when': None},
 {'conduction': ['worktree_add', 'select_initial_repair', 'select_evidence_repair'],
  'id': 'finalize_repair_result',
  'when': {'equals': 'ready', 'path': 'route', 'upstream': 'worktree_add'}},
 {'conduction': ['finalize_repair_result'],
  'id': 'pr_repair_fail_closed',
  'when': {'equals': 'fail_closed', 'path': 'route', 'upstream': 'finalize_repair_result'}},
 {'conduction': ['worktree_add', 'finalize_repair_result'],
  'id': 'relocalize_initial_repair',
  'when': {'equals': 'repaired', 'path': 'route', 'upstream': 'finalize_repair_result'}},
 {'conduction': ['worktree_add', 'finalize_repair_result', 'relocalize_initial_repair'],
  'id': 'assert_initial_repair_diff',
  'when': {'equals': 'repaired', 'path': 'route', 'upstream': 'finalize_repair_result'}},
 {'conduction': ['worktree_add', 'finalize_repair_result', 'assert_initial_repair_diff'],
  'id': 'commit_initial_repair',
  'when': {'equals': 'repaired', 'path': 'route', 'upstream': 'finalize_repair_result'}},
 {'conduction': ['worktree_add', 'commit_initial_repair', 'finalize_repair_result'],
  'id': 'test_local',
  'when': {'equals': 'repaired', 'path': 'route', 'upstream': 'finalize_repair_result'}},
 {'conduction': ['test_local', 'finalize_repair_result'], 'id': 'select_repair_test', 'when': None},
 {'conduction': ['worktree_add', 'test_local', 'select_repair_test'],
  'id': 'pr_test_repair_agent',
  'when': {'equals': 'fail', 'path': 'route', 'upstream': 'select_repair_test'}},
 {'conduction': ['select_repair_test', 'pr_test_repair_agent'],
  'id': 'validate_test_repair',
  'when': {'equals': 'fail', 'path': 'route', 'upstream': 'select_repair_test'}},
 {'conduction': ['select_repair_test', 'validate_test_repair'],
  'id': 'select_test_repair_result',
  'when': None},
 {'conduction': ['worktree_add', 'select_test_repair_result'],
  'id': 'relocalize_test_repair',
  'when': {'equals': 'repaired', 'path': 'route', 'upstream': 'select_test_repair_result'}},
 {'conduction': ['worktree_add', 'select_test_repair_result', 'relocalize_test_repair'],
  'id': 'assert_test_repair_diff',
  'when': {'equals': 'repaired', 'path': 'route', 'upstream': 'select_test_repair_result'}},
 {'conduction': ['worktree_add', 'select_test_repair_result', 'assert_test_repair_diff'],
  'id': 'commit_test_repair',
  'when': {'equals': 'repaired', 'path': 'route', 'upstream': 'select_test_repair_result'}},
 {'conduction': ['worktree_add', 'commit_test_repair', 'select_test_repair_result'],
  'id': 'test_local_recheck',
  'when': {'equals': 'repaired', 'path': 'route', 'upstream': 'select_test_repair_result'}},
 {'conduction': ['select_test_repair_result', 'test_local_recheck'],
  'id': 'select_repair_test_recheck',
  'when': None},
 {'conduction': ['finalize_repair_result', 'select_repair_test', 'select_repair_test_recheck'],
  'id': 'finalize_repair_tests',
  'when': None},
 {'conduction': ['finalize_repair_tests'],
  'id': 'pr_repair_terminal',
  'when': {'equals': 'terminal', 'path': 'route', 'upstream': 'finalize_repair_tests'}},
 {'conduction': ['worktree_add', 'finalize_repair_tests'],
  'id': 'assert_real_diff',
  'when': {'equals': 'publish', 'path': 'route', 'upstream': 'finalize_repair_tests'}},
 {'conduction': ['worktree_add',
                 'commit_initial_repair',
                 'commit_test_repair',
                 'test_local',
                 'test_local_recheck',
                 'finalize_repair_tests',
                 'assert_real_diff'],
  'id': 'push',
  'when': {'equals': 'publish', 'path': 'route', 'upstream': 'finalize_repair_tests'}},
 {'conduction': ['admit_pr_repair',
                 'finalize_repair_result',
                 'finalize_repair_tests',
                 'push',
                 'pr_repair_fail_closed',
                 'pr_repair_terminal'],
  'id': 'summarize_pr_repair',
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

