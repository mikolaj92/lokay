"""Native Fala host_run_package proofs for self_repair_entry."""
from __future__ import annotations

import pytest

_PATH_ID = 'self_repair_entry'
_EFFECTORS = [{'conduction': [], 'id': 'prepare_self_repair_entry', 'when': None},
 {'conduction': ['prepare_self_repair_entry'], 'id': 'classify_self_repair_entry', 'when': None},
 {'conduction': ['prepare_self_repair_entry', 'classify_self_repair_entry'],
  'id': 'record_self_repair_entry_start',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'classify_self_repair_entry'}},
 {'conduction': ['prepare_self_repair_entry', 'classify_self_repair_entry', 'record_self_repair_entry_start'],
  'id': 'run_authored_self_repair',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'classify_self_repair_entry'}},
 {'conduction': ['classify_self_repair_entry', 'run_authored_self_repair'],
  'id': 'record_authored_self_repair',
  'when': None},
 {'conduction': ['record_authored_self_repair'], 'id': 'classify_self_repair_entry_outcome', 'when': None},
 {'conduction': ['prepare_self_repair_entry', 'classify_self_repair_entry_outcome'],
  'id': 'write_self_repair_restart_marker',
  'when': {'equals': 'restart', 'path': 'route', 'upstream': 'classify_self_repair_entry_outcome'}},
 {'conduction': ['prepare_self_repair_entry',
                 'classify_self_repair_entry',
                 'classify_self_repair_entry_outcome',
                 'write_self_repair_restart_marker'],
  'id': 'select_self_repair_entry_result',
  'when': None},
 {'conduction': ['prepare_self_repair_entry', 'select_self_repair_entry_result'],
  'id': 'record_self_repair_entry_success',
  'when': {'equals': 'success', 'path': 'route', 'upstream': 'select_self_repair_entry_result'}},
 {'conduction': ['prepare_self_repair_entry', 'select_self_repair_entry_result'],
  'id': 'record_self_repair_entry_failure',
  'when': {'equals': 'failure', 'path': 'route', 'upstream': 'select_self_repair_entry_result'}},
 {'conduction': ['select_self_repair_entry_result',
                 'record_self_repair_entry_success',
                 'record_self_repair_entry_failure'],
  'id': 'self_repair_entry_terminal',
  'when': None}]
_MATCH = {'classify_self_repair_entry': {'route': 'run'},
 'classify_self_repair_entry_outcome': {'route': 'restart'},
 'select_self_repair_entry_result': {'route': 'success'}}
_MISS = {'classify_self_repair_entry': {'route': 'not-run'},
 'classify_self_repair_entry_outcome': {'route': 'not-restart'},
 'select_self_repair_entry_result': {'route': 'not-success'}}
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
