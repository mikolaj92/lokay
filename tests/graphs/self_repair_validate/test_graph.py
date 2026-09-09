"""Native Fala host_run_package proofs for self_repair_validate."""
from __future__ import annotations

import pytest

_PATH_ID = 'self_repair_validate'
_EFFECTORS = [{'conduction': [], 'id': 'read_self_repair_candidate_state', 'when': None},
 {'conduction': ['read_self_repair_candidate_state'],
  'id': 'classify_self_repair_candidate_diff',
  'when': None},
 {'conduction': ['classify_self_repair_candidate_diff'],
  'id': 'validate_self_repair_identity_request',
  'when': None},
 {'conduction': ['validate_self_repair_identity_request'],
  'id': 'inspect_self_repair_candidate_identity',
  'when': {'equals': 'inspect', 'path': 'route', 'upstream': 'validate_self_repair_identity_request'}},
 {'conduction': ['validate_self_repair_identity_request', 'inspect_self_repair_candidate_identity'],
  'id': 'select_self_repair_identity_gate',
  'when': None},
 {'conduction': ['select_self_repair_identity_gate'],
  'id': 'verify_self_repair_candidate_identity',
  'when': {'equals': 'identity', 'path': 'route', 'upstream': 'select_self_repair_identity_gate'}},
 {'conduction': ['select_self_repair_identity_gate', 'verify_self_repair_candidate_identity'],
  'id': 'run_self_repair_tests',
  'when': None},
 {'conduction': ['run_self_repair_tests'],
  'id': 'list_self_repair_untracked_paths',
  'when': {'equals': True, 'path': 'ok', 'upstream': 'run_self_repair_tests'}},
 {'conduction': ['list_self_repair_untracked_paths'],
  'id': 'self_repair_untracked_catalog',
  'when': {'equals': True, 'path': 'ok', 'upstream': 'list_self_repair_untracked_paths'}},
 {'conduction': ['self_repair_untracked_catalog'],
  'id': 'check_self_repair_tracked_working',
  'when': {'equals': True, 'path': 'ok', 'upstream': 'self_repair_untracked_catalog'}},
 {'conduction': ['check_self_repair_tracked_working'],
  'id': 'check_self_repair_tracked_cached',
  'when': {'equals': True, 'path': 'ok', 'upstream': 'check_self_repair_tracked_working'}},
 {'conduction': ['check_self_repair_tracked_cached'],
  'id': 'select_self_repair_committed_need',
  'when': {'equals': True, 'path': 'ok', 'upstream': 'check_self_repair_tracked_cached'}},
 {'conduction': ['select_self_repair_committed_need'],
  'id': 'check_self_repair_tracked_committed',
  'when': {'equals': 'has_base', 'path': 'route', 'upstream': 'select_self_repair_committed_need'}},
 {'conduction': ['check_self_repair_tracked_cached', 'check_self_repair_tracked_committed'],
  'id': 'select_self_repair_committed_gate',
  'when': {'equals': True, 'path': 'ok', 'upstream': 'check_self_repair_tracked_cached'}},
 {'conduction': ['select_self_repair_committed_gate'],
  'id': 'recheck_self_repair_identity',
  'when': {'equals': True, 'path': 'ok', 'upstream': 'select_self_repair_committed_gate'}},
 {'conduction': ['recheck_self_repair_identity'],
  'id': 'summarize_self_repair_validation',
  'when': {'equals': True, 'path': 'ok', 'upstream': 'recheck_self_repair_identity'}}]
_MATCH = {'check_self_repair_tracked_cached': {'ok': True},
 'check_self_repair_tracked_working': {'ok': True},
 'list_self_repair_untracked_paths': {'ok': True},
 'recheck_self_repair_identity': {'ok': True},
 'run_self_repair_tests': {'ok': True},
 'select_self_repair_committed_gate': {'ok': True},
 'select_self_repair_committed_need': {'route': 'has_base'},
 'select_self_repair_identity_gate': {'route': 'identity'},
 'self_repair_untracked_catalog': {'ok': True},
 'validate_self_repair_identity_request': {'route': 'inspect'}}
_MISS = {'check_self_repair_tracked_cached': {'ok': False},
 'check_self_repair_tracked_working': {'ok': False},
 'list_self_repair_untracked_paths': {'ok': False},
 'recheck_self_repair_identity': {'ok': False},
 'run_self_repair_tests': {'ok': False},
 'select_self_repair_committed_gate': {'ok': False},
 'select_self_repair_committed_need': {'route': 'not-has_base'},
 'select_self_repair_identity_gate': {'route': 'not-identity'},
 'self_repair_untracked_catalog': {'ok': False},
 'validate_self_repair_identity_request': {'route': 'not-inspect'}}
_MAX_TICKS = 64

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
