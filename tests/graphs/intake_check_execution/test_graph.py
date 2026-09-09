"""Native Fala host_run_package proofs for intake_check_execution."""
from __future__ import annotations

import pytest

_PATH_ID = 'intake_check_execution'
_EFFECTORS = [{'conduction': [], 'id': 'prepare_intake_check', 'when': None},
 {'conduction': ['prepare_intake_check'], 'id': 'read_intake_check_issue', 'when': None},
 {'conduction': ['prepare_intake_check', 'read_intake_check_issue'],
  'id': 'resolve_intake_check_clone',
  'when': None},
 {'conduction': ['prepare_intake_check', 'read_intake_check_issue'],
  'id': 'classify_intake_check_route',
  'when': None},
 {'conduction': ['read_intake_check_issue', 'classify_intake_check_route'],
  'id': 'run_intake_open_check',
  'when': {'equals': 'open', 'path': 'route', 'upstream': 'classify_intake_check_route'}},
 {'conduction': ['prepare_intake_check', 'read_intake_check_issue', 'classify_intake_check_route'],
  'id': 'run_intake_superseded_check',
  'when': {'equals': 'superseded', 'path': 'route', 'upstream': 'classify_intake_check_route'}},
 {'conduction': ['resolve_intake_check_clone', 'classify_intake_check_route'],
  'id': 'probe_intake_check_shape',
  'when': {'equals': 'shape', 'path': 'route', 'upstream': 'classify_intake_check_route'}},
 {'conduction': ['read_intake_check_issue', 'probe_intake_check_shape', 'classify_intake_check_route'],
  'id': 'run_intake_shape_check',
  'when': {'equals': 'shape', 'path': 'route', 'upstream': 'classify_intake_check_route'}},
 {'conduction': ['read_intake_check_issue', 'resolve_intake_check_clone', 'classify_intake_check_route'],
  'id': 'run_intake_satisfied_check',
  'when': {'equals': 'satisfied', 'path': 'route', 'upstream': 'classify_intake_check_route'}},
 {'conduction': ['read_intake_check_issue', 'classify_intake_check_route'],
  'id': 'run_intake_ambiguity_check',
  'when': {'equals': 'ambiguity', 'path': 'route', 'upstream': 'classify_intake_check_route'}},
 {'conduction': ['prepare_intake_check', 'classify_intake_check_route'],
  'id': 'parse_intake_covering_prs',
  'when': {'equals': 'duplicate_ai_pr', 'path': 'route', 'upstream': 'classify_intake_check_route'}},
 {'conduction': ['read_intake_check_issue', 'parse_intake_covering_prs', 'classify_intake_check_route'],
  'id': 'run_intake_duplicate_pr_check',
  'when': {'equals': 'duplicate_ai_pr', 'path': 'route', 'upstream': 'classify_intake_check_route'}},
 {'conduction': ['run_intake_open_check',
                 'run_intake_superseded_check',
                 'run_intake_shape_check',
                 'run_intake_satisfied_check',
                 'run_intake_ambiguity_check',
                 'run_intake_duplicate_pr_check',
                 'parse_intake_covering_prs'],
  'id': 'select_intake_check_result',
  'when': None},
 {'conduction': ['prepare_intake_check',
                 'read_intake_check_issue',
                 'resolve_intake_check_clone',
                 'select_intake_check_result'],
  'id': 'intake_check_terminal',
  'when': None}]
_MATCH = {'classify_intake_check_route': {'route': 'open'}}
_MISS = {'classify_intake_check_route': {'route': 'not-open'}}
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
