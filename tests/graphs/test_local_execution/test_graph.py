"""Native Fala host_run_package proofs for test_local_execution."""
from __future__ import annotations

import pytest

_PATH_ID = 'test_local_execution'
_EFFECTORS = [{'conduction': [], 'id': 'inspect_test_declaration', 'when': None},
 {'conduction': ['inspect_test_declaration'], 'id': 'read_test_green_cache', 'when': None},
 {'conduction': ['inspect_test_declaration', 'read_test_green_cache'],
  'id': 'run_declared_tests',
  'when': {'equals': 'miss', 'path': 'route', 'upstream': 'read_test_green_cache'}},
 {'conduction': ['run_declared_tests'], 'id': 'select_declared_test_outcome', 'when': None},
 {'conduction': ['inspect_test_declaration', 'select_declared_test_outcome'],
  'id': 'derive_changed_test_scope',
  'when': None},
 {'conduction': ['inspect_test_declaration', 'derive_changed_test_scope'],
  'id': 'run_changed_scope_tests',
  'when': {'equals': 'scope', 'path': 'route', 'upstream': 'derive_changed_test_scope'}},
 {'conduction': ['run_declared_tests', 'run_changed_scope_tests'],
  'id': 'select_green_test_result',
  'when': None},
 {'conduction': ['inspect_test_declaration', 'read_test_green_cache', 'select_green_test_result'],
  'id': 'write_test_green_cache',
  'when': None},
 {'conduction': ['inspect_test_declaration',
                 'read_test_green_cache',
                 'run_declared_tests',
                 'run_changed_scope_tests',
                 'write_test_green_cache'],
  'id': 'classify_test_terminal',
  'when': None},
 {'conduction': ['inspect_test_declaration',
                 'read_test_green_cache',
                 'run_declared_tests',
                 'run_changed_scope_tests',
                 'write_test_green_cache',
                 'classify_test_terminal'],
  'id': 'build_test_terminal_inspection',
  'when': {'equals': 'inspection', 'path': 'kind', 'upstream': 'classify_test_terminal'}},
 {'conduction': ['inspect_test_declaration',
                 'read_test_green_cache',
                 'run_declared_tests',
                 'run_changed_scope_tests',
                 'write_test_green_cache',
                 'classify_test_terminal'],
  'id': 'build_test_terminal_cached',
  'when': {'equals': 'cached', 'path': 'kind', 'upstream': 'classify_test_terminal'}},
 {'conduction': ['inspect_test_declaration',
                 'read_test_green_cache',
                 'run_declared_tests',
                 'run_changed_scope_tests',
                 'write_test_green_cache',
                 'classify_test_terminal'],
  'id': 'build_test_terminal_green',
  'when': {'equals': 'green', 'path': 'kind', 'upstream': 'classify_test_terminal'}},
 {'conduction': ['inspect_test_declaration',
                 'read_test_green_cache',
                 'run_declared_tests',
                 'run_changed_scope_tests',
                 'write_test_green_cache',
                 'classify_test_terminal'],
  'id': 'build_test_terminal_red',
  'when': {'equals': 'red', 'path': 'kind', 'upstream': 'classify_test_terminal'}},
 {'conduction': ['build_test_terminal_inspection',
                 'build_test_terminal_cached',
                 'build_test_terminal_green',
                 'build_test_terminal_red'],
  'id': 'select_test_terminal',
  'when': None}]
_MATCH = {'classify_test_terminal': {'kind': 'inspection'},
 'derive_changed_test_scope': {'route': 'scope'},
 'read_test_green_cache': {'route': 'miss'}}
_MISS = {'classify_test_terminal': {'kind': 'not-inspection'},
 'derive_changed_test_scope': {'route': 'not-scope'},
 'read_test_green_cache': {'route': 'not-miss'}}
_MAX_TICKS = 56

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
