"""Native Fala host_run_package proofs for status_snapshot."""
from __future__ import annotations

import pytest

_PATH_ID = 'status_snapshot'
_EFFECTORS = [{'conduction': [], 'id': 'read_status_config', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'classify_status_readiness', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'read_status_clone_facts', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'read_status_lease', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'read_status_pass_receipt', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'read_status_work_units', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'read_status_repo_locks', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'describe_status_graphs', 'when': None},
 {'conduction': ['read_status_config'],
  'id': 'run_status_preflight',
  'when': {'equals': True, 'path': 'preflight_requested', 'upstream': 'read_status_config'}},
 {'conduction': ['read_status_config', 'run_status_preflight'],
  'id': 'record_status_preflight',
  'when': None},
 {'conduction': ['read_status_config',
                 'classify_status_readiness',
                 'read_status_clone_facts',
                 'read_status_lease',
                 'read_status_pass_receipt',
                 'read_status_work_units',
                 'read_status_repo_locks',
                 'describe_status_graphs',
                 'record_status_preflight'],
  'id': 'reduce_status_snapshot',
  'when': None},
 {'conduction': ['reduce_status_snapshot'], 'id': 'status_snapshot_terminal', 'when': None}]
_MATCH = {'read_status_config': {'preflight_requested': True}}
_MISS = {'read_status_config': {'preflight_requested': False}}
_MAX_TICKS = 48

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
