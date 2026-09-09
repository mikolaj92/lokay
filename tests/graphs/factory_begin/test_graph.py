"""Native Fala host_run_package proofs for factory_begin."""
from __future__ import annotations

import pytest

_PATH_ID = 'factory_begin'
_EFFECTORS = [{'conduction': [], 'id': 'probe_factory_host', 'when': None},
 {'conduction': ['probe_factory_host'], 'id': 'load_factory_config', 'when': None},
 {'conduction': ['load_factory_config'], 'id': 'select_factory_scope', 'when': None},
 {'conduction': ['load_factory_config'], 'id': 'read_factory_stuck', 'when': None},
 {'conduction': ['load_factory_config', 'select_factory_scope'],
  'id': 'create_factory_pass_dir',
  'when': None},
 {'conduction': ['load_factory_config',
                 'select_factory_scope',
                 'read_factory_stuck',
                 'create_factory_pass_dir'],
  'id': 'build_factory_begin_state',
  'when': None},
 {'conduction': ['read_factory_stuck'], 'id': 'build_factory_working_state', 'when': None},
 {'conduction': ['build_factory_working_state'], 'id': 'seed_factory_occupancy', 'when': None},
 {'conduction': ['build_factory_begin_state', 'seed_factory_occupancy', 'read_factory_stuck'],
  'id': 'attach_factory_stuck',
  'when': None},
 {'conduction': ['create_factory_pass_dir', 'attach_factory_stuck'],
  'id': 'persist_factory_begin_state',
  'when': None},
 {'conduction': ['create_factory_pass_dir', 'attach_factory_stuck', 'persist_factory_begin_state'],
  'id': 'persist_factory_working_state',
  'when': None},
 {'conduction': ['probe_factory_host',
                 'read_factory_stuck',
                 'create_factory_pass_dir',
                 'attach_factory_stuck',
                 'persist_factory_working_state'],
  'id': 'persist_factory_tick',
  'when': None},
 {'conduction': ['persist_factory_tick'], 'id': 'classify_leftover_remaining', 'when': None},
 {'conduction': ['persist_factory_tick', 'classify_leftover_remaining'],
  'id': 'merge_leftover_remaining',
  'when': None}]
_MATCH = {}
_MISS = {}
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
