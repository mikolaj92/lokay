"""Native Fala host_run_package proofs for local_repair_execution."""
from __future__ import annotations

import pytest

_PATH_ID = 'local_repair_execution'
_EFFECTORS = [{'conduction': [], 'id': 'prepare_local_repair_request', 'when': None},
 {'conduction': ['prepare_local_repair_request'], 'id': 'repair_agent', 'when': None},
 {'conduction': ['repair_agent', 'prepare_local_repair_request'],
  'id': 'validate_repair_result',
  'when': None},
 {'conduction': ['prepare_local_repair_request', 'validate_repair_result'],
  'id': 'local_repair_retry_agent',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_repair_result'}},
 {'conduction': ['validate_repair_result', 'local_repair_retry_agent'],
  'id': 'validate_local_repair_retry',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_repair_result'}},
 {'conduction': ['validate_repair_result', 'validate_local_repair_retry'],
  'id': 'select_repair_result',
  'when': None},
 {'conduction': ['prepare_local_repair_request', 'select_repair_result'],
  'id': 'assert_repair_diff',
  'when': {'equals': 'repaired', 'path': 'route', 'upstream': 'select_repair_result'}},
 {'conduction': ['prepare_local_repair_request', 'select_repair_result', 'assert_repair_diff'],
  'id': 'commit_repair',
  'when': {'equals': 'repaired', 'path': 'route', 'upstream': 'select_repair_result'}},
 {'conduction': ['prepare_local_repair_request',
                 'commit_repair',
                 'repair_agent',
                 'local_repair_retry_agent',
                 'select_repair_result'],
  'id': 'test_local_recheck',
  'when': {'equals': 'repaired', 'path': 'route', 'upstream': 'select_repair_result'}},
 {'conduction': ['test_local_recheck', 'select_repair_result'],
  'id': 'select_local_test_recheck',
  'when': None},
 {'conduction': ['select_repair_result', 'select_local_test_recheck'],
  'id': 'local_repair_terminal',
  'when': None}]
_MATCH = {'select_repair_result': {'route': 'repaired'}, 'validate_repair_result': {'route': 'retry'}}
_MISS = {'select_repair_result': {'route': 'not-repaired'}, 'validate_repair_result': {'route': 'not-retry'}}
_MAX_TICKS = 44

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
