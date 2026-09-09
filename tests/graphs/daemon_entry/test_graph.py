"""Native Fala host_run_package proofs for daemon_entry."""
from __future__ import annotations

import pytest

_PATH_ID = 'daemon_entry'
_EFFECTORS = [{'conduction': [], 'id': 'classify_daemon_preflight', 'when': None},
 {'conduction': ['classify_daemon_preflight'],
  'id': 'run_daemon_product_cycle',
  'when': {'equals': 'product', 'path': 'route', 'upstream': 'classify_daemon_preflight'}},
 {'conduction': ['classify_daemon_preflight'],
  'id': 'run_initial_self_repair',
  'when': {'equals': 'repair', 'path': 'route', 'upstream': 'classify_daemon_preflight'}},
 {'conduction': ['classify_daemon_preflight', 'run_daemon_product_cycle', 'run_initial_self_repair'],
  'id': 'daemon_entry_terminal',
  'when': None}]
_MATCH = {'classify_daemon_preflight': {'route': 'product'}}
_MISS = {'classify_daemon_preflight': {'route': 'not-product'}}
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
