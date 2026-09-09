"""Native Fala host_run_package proofs for pr_repair."""
from __future__ import annotations

import pytest

_PATH_ID = 'pr_repair'
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
_MATCH = {'finalize_repair_result': {'route': 'fail_closed'},
 'finalize_repair_tests': {'route': 'terminal'},
 'localize': {'route': 'ready'},
 'select_initial_repair': {'evidence_kind': 'pr_metadata', 'route': 'evidence'},
 'select_repair_test': {'route': 'fail'},
 'select_test_repair_result': {'route': 'repaired'},
 'validate_initial_repair': {'route': 'retry'},
 'worktree_add': {'route': 'ready'}}
_MISS = {'finalize_repair_result': {'route': 'not-fail_closed'},
 'finalize_repair_tests': {'route': 'not-terminal'},
 'localize': {'route': 'not-ready'},
 'select_initial_repair': {'evidence_kind': 'not-pr_metadata', 'route': 'not-evidence'},
 'select_repair_test': {'route': 'not-fail'},
 'select_test_repair_result': {'route': 'not-repaired'},
 'validate_initial_repair': {'route': 'not-retry'},
 'worktree_add': {'route': 'not-ready'}}
_MAX_TICKS = 152

def test_model_match_and_miss_differ_when_branches_exist():
    from support.graph_model import run_model
    matched = run_model(_EFFECTORS, _MATCH)
    missed = run_model(_EFFECTORS, _MISS)
    if _MATCH:
        assert matched != missed
    for item in _EFFECTORS:
        assert matched[item["id"]] in {"succeeded", "skipped"}
        assert missed[item["id"]] in {"succeeded", "skipped"}

def test_native_match_skips_nonmatching_adapters(tmp_path):
    from support.graph_model import node_status_map, run_model
    from support.native_path import run_overridden_path
    expected = run_model(_EFFECTORS, _MATCH)
    result = run_overridden_path(tmp_path, _PATH_ID, _MATCH, run_id="match", max_ticks=_MAX_TICKS)
    assert result.get("run_status") == "completed"
    native = node_status_map(result)
    assert native == expected
    ran = set(result.get("_ran") or [])
    for nid, status in native.items():
        if status == "skipped":
            assert nid not in ran
        elif status == "succeeded":
            assert nid in ran

def test_native_miss_skips_matching_when_branches(tmp_path):
    from support.graph_model import node_status_map, run_model
    from support.native_path import run_overridden_path
    if not _MISS:
        pytest.skip("path has no when branches")
    expected = run_model(_EFFECTORS, _MISS)
    result = run_overridden_path(tmp_path, _PATH_ID, _MISS, run_id="miss", max_ticks=_MAX_TICKS)
    assert result.get("run_status") == "completed"
    native = node_status_map(result)
    assert native == expected
    ran = set(result.get("_ran") or [])
    for nid, status in native.items():
        if status == "skipped":
            assert nid not in ran
