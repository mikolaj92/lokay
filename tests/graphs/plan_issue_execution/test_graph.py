"""Native Fala host_run_package proofs for plan_issue_execution."""
from __future__ import annotations

import pytest

_PATH_ID = 'plan_issue_execution'
_EFFECTORS = [{'conduction': [], 'id': 'prepare_issue_plan_request', 'when': None},
 {'conduction': ['prepare_issue_plan_request'], 'id': 'build_issue_approach', 'when': None},
 {'conduction': ['prepare_issue_plan_request', 'build_issue_approach'],
  'id': 'authorize_issue_plan_write',
  'when': None},
 {'conduction': ['prepare_issue_plan_request', 'build_issue_approach', 'authorize_issue_plan_write'],
  'id': 'write_issue_approach',
  'when': {'equals': 'write', 'path': 'route', 'upstream': 'authorize_issue_plan_write'}},
 {'conduction': ['authorize_issue_plan_write', 'write_issue_approach'],
  'id': 'record_issue_approach_write',
  'when': None},
 {'conduction': ['prepare_issue_plan_request',
                 'build_issue_approach',
                 'authorize_issue_plan_write',
                 'record_issue_approach_write'],
  'id': 'issue_plan_terminal',
  'when': None}]
_MATCH = {'authorize_issue_plan_write': {'route': 'write'}}
_MISS = {'authorize_issue_plan_write': {'route': 'not-write'}}
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
