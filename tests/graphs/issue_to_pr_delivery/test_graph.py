"""Native Fala host_run_package proofs for issue_to_pr_delivery."""
from __future__ import annotations

import pytest

_PATH_ID = 'issue_to_pr_delivery'
_EFFECTORS = [{'conduction': [], 'id': 'get_issue', 'when': None},
 {'conduction': ['get_issue'], 'id': 'resolve_implementation_issue', 'when': None},
 {'conduction': ['get_issue', 'resolve_implementation_issue'],
  'id': 'assign_issue',
  'when': {'equals': 'open', 'path': 'route', 'upstream': 'resolve_implementation_issue'}},
 {'conduction': ['get_issue', 'resolve_implementation_issue'],
  'id': 'stage_implementing',
  'when': {'equals': 'open', 'path': 'route', 'upstream': 'resolve_implementation_issue'}},
 {'conduction': ['get_issue', 'resolve_implementation_issue'],
  'id': 'make_branch',
  'when': {'equals': 'open', 'path': 'route', 'upstream': 'resolve_implementation_issue'}},
 {'conduction': ['get_issue', 'make_branch', 'assign_issue', 'stage_implementing'],
  'id': 'worktree_add',
  'when': None},
 {'conduction': ['get_issue', 'worktree_add'],
  'id': 'map_repo',
  'when': {'equals': 'ready', 'path': 'route', 'upstream': 'worktree_add'}},
 {'conduction': ['get_issue', 'make_branch', 'worktree_add', 'map_repo'],
  'id': 'plan_issue',
  'when': {'equals': 'ready', 'path': 'route', 'upstream': 'worktree_add'}},
 {'conduction': ['get_issue', 'make_branch', 'worktree_add', 'map_repo', 'plan_issue'],
  'id': 'localize',
  'when': {'equals': 'ready', 'path': 'route', 'upstream': 'worktree_add'}},
 {'conduction': ['get_issue', 'localize'], 'id': 'cycle_start', 'when': None},
 {'conduction': ['get_issue', 'worktree_add', 'plan_issue', 'localize'],
  'id': 'prepare_acceptance',
  'when': {'equals': 'ready', 'path': 'route', 'upstream': 'localize'}},
 {'conduction': ['get_issue',
                 'make_branch',
                 'worktree_add',
                 'map_repo',
                 'plan_issue',
                 'localize',
                 'cycle_start',
                 'prepare_acceptance'],
  'id': 'coding_execution',
  'when': {'equals': 'ready', 'path': 'route', 'upstream': 'localize'}},
 {'conduction': ['worktree_add', 'localize', 'coding_execution'],
  'id': 'relocalize_off_goal',
  'when': {'equals': 'implemented', 'path': 'route', 'upstream': 'coding_execution'}},
 {'conduction': ['worktree_add', 'coding_execution', 'relocalize_off_goal'],
  'id': 'assert_implementation_diff',
  'when': {'equals': 'implemented', 'path': 'route', 'upstream': 'coding_execution'}},
 {'conduction': ['get_issue', 'worktree_add', 'coding_execution', 'assert_implementation_diff'],
  'id': 'commit_implementation',
  'when': {'equals': 'implemented', 'path': 'route', 'upstream': 'coding_execution'}},
 {'conduction': ['worktree_add', 'commit_implementation', 'coding_execution'],
  'id': 'rebase_onto_base',
  'when': {'equals': 'implemented', 'path': 'route', 'upstream': 'coding_execution'}},
 {'conduction': ['worktree_add', 'commit_implementation', 'rebase_onto_base', 'coding_execution'],
  'id': 'test_local_execution',
  'when': {'equals': 'implemented', 'path': 'route', 'upstream': 'coding_execution'}},
 {'conduction': ['test_local_execution', 'coding_execution'], 'id': 'select_local_test', 'when': None},
 {'conduction': ['get_issue',
                 'worktree_add',
                 'coding_execution',
                 'commit_implementation',
                 'test_local_execution',
                 'select_local_test'],
  'id': 'local_repair_execution',
  'when': {'equals': 'fail', 'path': 'route', 'upstream': 'select_local_test'}},
 {'conduction': ['select_local_test', 'local_repair_execution', 'coding_execution'],
  'id': 'finalize_local_tests',
  'when': None},
 {'conduction': ['finalize_local_tests'], 'id': 'local_verification_terminal', 'when': None},
 {'conduction': ['finalize_local_tests'],
  'id': 'coding_repair_terminal',
  'when': {'equals': 'repair_terminal', 'path': 'route', 'upstream': 'finalize_local_tests'}},
 {'conduction': ['prepare_acceptance',
                 'worktree_add',
                 'finalize_local_tests',
                 'test_local_execution',
                 'local_repair_execution'],
  'id': 'verify_acceptance',
  'when': {'equals': 'publish', 'path': 'route', 'upstream': 'finalize_local_tests'}},
 {'conduction': ['get_issue',
                 'worktree_add',
                 'coding_execution',
                 'commit_implementation',
                 'verify_acceptance'],
  'id': 'acceptance_repair_execution',
  'when': {'equals': 'repair', 'path': 'route', 'upstream': 'verify_acceptance'}},
 {'conduction': ['prepare_acceptance',
                 'worktree_add',
                 'verify_acceptance',
                 'acceptance_repair_execution',
                 'test_local_execution'],
  'id': 'verify_acceptance_recheck',
  'when': {'equals': True, 'path': 'ok', 'upstream': 'acceptance_repair_execution'}},
 {'conduction': ['verify_acceptance', 'acceptance_repair_execution', 'verify_acceptance_recheck'],
  'id': 'finalize_acceptance',
  'when': {'equals': True, 'path': 'ok', 'upstream': 'verify_acceptance'}},
 {'conduction': ['worktree_add',
                 'finalize_local_tests',
                 'finalize_acceptance',
                 'verify_acceptance',
                 'local_repair_execution',
                 'commit_implementation'],
  'id': 'list_dirty_stamp_paths',
  'when': {'equals': 'publish', 'path': 'route', 'upstream': 'finalize_acceptance'}},
 {'conduction': ['get_issue', 'worktree_add', 'list_dirty_stamp_paths', 'verify_acceptance'],
  'id': 'commit_stamp_files',
  'when': {'equals': 'dirty', 'path': 'route', 'upstream': 'list_dirty_stamp_paths'}},
 {'conduction': ['worktree_add',
                 'list_dirty_stamp_paths',
                 'commit_stamp_files',
                 'finalize_acceptance',
                 'verify_acceptance'],
  'id': 'assert_stamps_committed',
  'when': {'equals': 'publish', 'path': 'route', 'upstream': 'finalize_acceptance'}},
 {'conduction': ['finalize_local_tests',
                 'local_verification_terminal',
                 'finalize_acceptance',
                 'verify_acceptance',
                 'assert_stamps_committed'],
  'id': 'select_publish_gate',
  'when': {'equals': 'publish', 'path': 'route', 'upstream': 'assert_stamps_committed'}},
 {'conduction': ['worktree_add',
                 'finalize_local_tests',
                 'relocalize_off_goal',
                 'verify_acceptance',
                 'select_publish_gate'],
  'id': 'assert_real_diff',
  'when': {'equals': 'publish', 'path': 'route', 'upstream': 'select_publish_gate'}},
 {'conduction': ['make_branch',
                 'worktree_add',
                 'commit_implementation',
                 'local_repair_execution',
                 'finalize_local_tests',
                 'finalize_acceptance',
                 'verify_acceptance',
                 'assert_stamps_committed',
                 'select_publish_gate',
                 'assert_real_diff'],
  'id': 'push',
  'when': {'equals': 'publish', 'path': 'route', 'upstream': 'select_publish_gate'}},
 {'conduction': ['get_issue',
                 'make_branch',
                 'coding_execution',
                 'finalize_local_tests',
                 'assert_real_diff',
                 'push',
                 'finalize_acceptance',
                 'verify_acceptance',
                 'assert_stamps_committed',
                 'select_publish_gate'],
  'id': 'pr_create',
  'when': {'equals': 'publish', 'path': 'route', 'upstream': 'select_publish_gate'}},
 {'conduction': ['get_issue', 'pr_create', 'cycle_start'], 'id': 'cycle_end', 'when': None},
 {'conduction': ['get_issue', 'pr_create'], 'id': 'stage_pr_open', 'when': None},
 {'conduction': ['get_issue', 'pr_create', 'stage_pr_open'], 'id': 'list_prs', 'when': None},
 {'conduction': ['get_issue', 'list_prs', 'pr_create'], 'id': 'pr_label', 'when': None},
 {'conduction': ['make_branch',
                 'coding_execution',
                 'finalize_local_tests',
                 'finalize_acceptance',
                 'verify_acceptance',
                 'pr_create',
                 'pr_label'],
  'id': 'summarize_issue_delivery',
  'when': None}]
_MATCH = {'acceptance_repair_execution': {'ok': True},
 'assert_stamps_committed': {'route': 'publish'},
 'coding_execution': {'route': 'implemented'},
 'finalize_acceptance': {'route': 'publish'},
 'finalize_local_tests': {'route': 'repair_terminal'},
 'list_dirty_stamp_paths': {'route': 'dirty'},
 'localize': {'route': 'ready'},
 'resolve_implementation_issue': {'route': 'open'},
 'select_local_test': {'route': 'fail'},
 'select_publish_gate': {'route': 'publish'},
 'verify_acceptance': {'ok': True, 'route': 'repair'},
 'worktree_add': {'route': 'ready'}}
_MISS = {'acceptance_repair_execution': {'ok': False},
 'assert_stamps_committed': {'route': 'not-publish'},
 'coding_execution': {'route': 'not-implemented'},
 'finalize_acceptance': {'route': 'not-publish'},
 'finalize_local_tests': {'route': 'not-repair_terminal'},
 'list_dirty_stamp_paths': {'route': 'not-dirty'},
 'localize': {'route': 'not-ready'},
 'resolve_implementation_issue': {'route': 'not-open'},
 'select_local_test': {'route': 'not-fail'},
 'select_publish_gate': {'route': 'not-publish'},
 'verify_acceptance': {'ok': False, 'route': 'not-repair'},
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
