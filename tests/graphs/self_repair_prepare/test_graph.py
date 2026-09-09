"""Native Fala host_run_package proofs for self_repair_prepare."""
from __future__ import annotations

import pytest

_PATH_ID = 'self_repair_prepare'
_EFFECTORS = [{'conduction': [], 'id': 'resolve_self_repair_checkout', 'when': None},
 {'conduction': ['resolve_self_repair_checkout'], 'id': 'check_self_repair_mutation_gate', 'when': None},
 {'conduction': ['check_self_repair_mutation_gate'],
  'id': 'verify_self_repair_origin',
  'when': {'equals': 'live', 'path': 'route', 'upstream': 'check_self_repair_mutation_gate'}},
 {'conduction': ['check_self_repair_mutation_gate', 'verify_self_repair_origin'],
  'id': 'select_self_repair_origin_gate',
  'when': None},
 {'conduction': ['select_self_repair_origin_gate'],
  'id': 'fetch_self_repair_main',
  'when': {'equals': 'verified', 'path': 'route', 'upstream': 'select_self_repair_origin_gate'}},
 {'conduction': ['select_self_repair_origin_gate', 'fetch_self_repair_main'],
  'id': 'select_self_repair_fetch_gate',
  'when': None},
 {'conduction': ['select_self_repair_fetch_gate'],
  'id': 'find_published_self_repair',
  'when': {'equals': 'fetched', 'path': 'route', 'upstream': 'select_self_repair_fetch_gate'}},
 {'conduction': ['check_self_repair_mutation_gate',
                 'select_self_repair_fetch_gate',
                 'find_published_self_repair'],
  'id': 'select_self_repair_publish_gate',
  'when': None},
 {'conduction': ['select_self_repair_publish_gate'],
  'id': 'read_self_repair_base',
  'when': {'equals': 'unpublished', 'path': 'route', 'upstream': 'select_self_repair_publish_gate'}},
 {'conduction': ['select_self_repair_publish_gate', 'read_self_repair_base'],
  'id': 'select_self_repair_base_gate',
  'when': None},
 {'conduction': ['select_self_repair_base_gate'],
  'id': 'inspect_self_repair_ownership',
  'when': {'equals': 'inspect', 'path': 'route', 'upstream': 'select_self_repair_base_gate'}},
 {'conduction': ['select_self_repair_base_gate', 'inspect_self_repair_ownership'],
  'id': 'select_self_repair_ownership_gate',
  'when': None},
 {'conduction': ['select_self_repair_ownership_gate'],
  'id': 'inspect_self_repair_changes',
  'when': {'equals': 'owned', 'path': 'route', 'upstream': 'select_self_repair_ownership_gate'}},
 {'conduction': ['select_self_repair_ownership_gate', 'inspect_self_repair_changes'],
  'id': 'select_self_repair_changes_gate',
  'when': None},
 {'conduction': ['select_self_repair_changes_gate'],
  'id': 'validate_self_repair_change_shape',
  'when': {'equals': 'changes', 'path': 'route', 'upstream': 'select_self_repair_changes_gate'}},
 {'conduction': ['select_self_repair_changes_gate', 'validate_self_repair_change_shape'],
  'id': 'select_self_repair_shape_gate',
  'when': None},
 {'conduction': ['select_self_repair_shape_gate'],
  'id': 'inspect_self_repair_commit',
  'when': {'equals': 'commit_facts', 'path': 'route', 'upstream': 'select_self_repair_shape_gate'}},
 {'conduction': ['select_self_repair_shape_gate', 'inspect_self_repair_commit'],
  'id': 'select_self_repair_commit_gate',
  'when': None},
 {'conduction': ['select_self_repair_commit_gate'],
  'id': 'validate_self_repair_commit',
  'when': {'equals': 'commit', 'path': 'route', 'upstream': 'select_self_repair_commit_gate'}},
 {'conduction': ['select_self_repair_commit_gate', 'validate_self_repair_commit'],
  'id': 'select_self_repair_commit_validation_gate',
  'when': None},
 {'conduction': ['select_self_repair_commit_validation_gate'],
  'id': 'inspect_self_repair_ancestry',
  'when': {'equals': 'ancestry', 'path': 'route', 'upstream': 'select_self_repair_commit_validation_gate'}},
 {'conduction': ['select_self_repair_base_gate',
                 'select_self_repair_ownership_gate',
                 'select_self_repair_changes_gate',
                 'select_self_repair_shape_gate',
                 'select_self_repair_commit_validation_gate',
                 'inspect_self_repair_ancestry'],
  'id': 'select_self_repair_worktree_route',
  'when': None},
 {'conduction': ['select_self_repair_worktree_route'],
  'id': 'remove_self_repair_worktree',
  'when': {'equals': 'remove', 'path': 'route', 'upstream': 'select_self_repair_worktree_route'}},
 {'conduction': ['select_self_repair_worktree_route', 'remove_self_repair_worktree'],
  'id': 'select_self_repair_remove_outcome',
  'when': None},
 {'conduction': ['select_self_repair_remove_outcome'],
  'id': 'create_self_repair_worktree',
  'when': {'equals': 'create_requested', 'path': 'route', 'upstream': 'select_self_repair_remove_outcome'}},
 {'conduction': ['resolve_self_repair_checkout',
                 'check_self_repair_mutation_gate',
                 'select_self_repair_publish_gate',
                 'select_self_repair_base_gate',
                 'select_self_repair_worktree_route',
                 'select_self_repair_remove_outcome',
                 'create_self_repair_worktree'],
  'id': 'select_self_repair_prepare_result',
  'when': None},
 {'conduction': ['select_self_repair_prepare_result'], 'id': 'summarize_self_repair_prepare', 'when': None}]
_MATCH = {'check_self_repair_mutation_gate': {'route': 'live'},
 'select_self_repair_base_gate': {'route': 'inspect'},
 'select_self_repair_changes_gate': {'route': 'changes'},
 'select_self_repair_commit_gate': {'route': 'commit'},
 'select_self_repair_commit_validation_gate': {'route': 'ancestry'},
 'select_self_repair_fetch_gate': {'route': 'fetched'},
 'select_self_repair_origin_gate': {'route': 'verified'},
 'select_self_repair_ownership_gate': {'route': 'owned'},
 'select_self_repair_publish_gate': {'route': 'unpublished'},
 'select_self_repair_remove_outcome': {'route': 'create_requested'},
 'select_self_repair_shape_gate': {'route': 'commit_facts'},
 'select_self_repair_worktree_route': {'route': 'remove'}}
_MISS = {'check_self_repair_mutation_gate': {'route': 'not-live'},
 'select_self_repair_base_gate': {'route': 'not-inspect'},
 'select_self_repair_changes_gate': {'route': 'not-changes'},
 'select_self_repair_commit_gate': {'route': 'not-commit'},
 'select_self_repair_commit_validation_gate': {'route': 'not-ancestry'},
 'select_self_repair_fetch_gate': {'route': 'not-fetched'},
 'select_self_repair_origin_gate': {'route': 'not-verified'},
 'select_self_repair_ownership_gate': {'route': 'not-owned'},
 'select_self_repair_publish_gate': {'route': 'not-unpublished'},
 'select_self_repair_remove_outcome': {'route': 'not-create_requested'},
 'select_self_repair_shape_gate': {'route': 'not-commit_facts'},
 'select_self_repair_worktree_route': {'route': 'not-remove'}}
_MAX_TICKS = 108

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
