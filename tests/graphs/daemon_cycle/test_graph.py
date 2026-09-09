"""Native Fala host_run_package proofs for daemon_cycle."""
from __future__ import annotations

import pytest

_PATH_ID = 'daemon_cycle'
_EFFECTORS = [{'conduction': [], 'id': 'last_pass_moving', 'when': None},
 {'conduction': ['last_pass_moving'], 'id': 'select_repair_route', 'when': None},
 {'conduction': ['select_repair_route'],
  'id': 'recovery_incident',
  'when': {'equals': 'repair', 'path': 'route', 'upstream': 'select_repair_route'}},
 {'conduction': ['select_repair_route', 'recovery_incident'],
  'id': 'recovery_run_self_repair',
  'when': {'equals': 'repair', 'path': 'route', 'upstream': 'select_repair_route'}},
 {'conduction': ['select_repair_route', 'recovery_run_self_repair'],
  'id': 'recovery_factory',
  'when': {'equals': 'factory', 'path': 'route', 'upstream': 'select_repair_route'}},
 {'conduction': ['select_repair_route', 'recovery_factory', 'recovery_run_self_repair'],
  'id': 'summarize_daemon_cycle',
  'when': None}]
_MATCH = {'select_repair_route': {'route': 'repair'}}
_MISS = {'select_repair_route': {'route': 'not-repair'}}
_MAX_TICKS = 32

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
