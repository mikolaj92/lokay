"""Native Fala host_run_package proofs for pr_create_execution."""
from __future__ import annotations

import pytest

_PATH_ID = 'pr_create_execution'
_EFFECTORS = [{'conduction': [], 'id': 'prepare_pr_create_request', 'when': None},
 {'conduction': ['prepare_pr_create_request'], 'id': 'find_existing_delivery_pr', 'when': None},
 {'conduction': ['find_existing_delivery_pr'], 'id': 'record_existing_delivery_pr', 'when': None},
 {'conduction': ['prepare_pr_create_request', 'record_existing_delivery_pr'],
  'id': 'read_pr_create_issue',
  'when': {'equals': 'none', 'path': 'route', 'upstream': 'record_existing_delivery_pr'}},
 {'conduction': ['record_existing_delivery_pr', 'read_pr_create_issue'],
  'id': 'classify_pr_create_issue',
  'when': None},
 {'conduction': ['prepare_pr_create_request', 'classify_pr_create_issue'],
  'id': 'create_pull_request_effect',
  'when': {'equals': 'create', 'path': 'route', 'upstream': 'classify_pr_create_issue'}},
 {'conduction': ['prepare_pr_create_request',
                 'record_existing_delivery_pr',
                 'read_pr_create_issue',
                 'classify_pr_create_issue',
                 'create_pull_request_effect'],
  'id': 'pr_create_terminal',
  'when': None}]
_MATCH = {'classify_pr_create_issue': {'route': 'create'}, 'record_existing_delivery_pr': {'route': 'none'}}
_MISS = {'classify_pr_create_issue': {'route': 'not-create'}, 'record_existing_delivery_pr': {'route': 'not-none'}}
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
