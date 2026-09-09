"""Native Fala host_run_package proofs for issue_split."""
from __future__ import annotations

import pytest

_PATH_ID = 'issue_split'
_EFFECTORS = [{'conduction': [], 'id': 'get_issue', 'when': None},
 {'conduction': ['get_issue'], 'id': 'plan_issue_split', 'when': None},
 {'conduction': ['get_issue', 'plan_issue_split'],
  'id': 'create_issue_split_child_1',
  'when': {'equals': 'present', 'path': 'child_1', 'upstream': 'plan_issue_split'}},
 {'conduction': ['get_issue', 'plan_issue_split', 'create_issue_split_child_1'],
  'id': 'create_issue_split_child_2',
  'when': {'equals': 'present', 'path': 'child_2', 'upstream': 'plan_issue_split'}},
 {'conduction': ['get_issue', 'plan_issue_split', 'create_issue_split_child_2'],
  'id': 'create_issue_split_child_3',
  'when': {'equals': 'present', 'path': 'child_3', 'upstream': 'plan_issue_split'}},
 {'conduction': ['get_issue', 'plan_issue_split', 'create_issue_split_child_3'],
  'id': 'create_issue_split_child_4',
  'when': {'equals': 'present', 'path': 'child_4', 'upstream': 'plan_issue_split'}},
 {'conduction': ['get_issue', 'plan_issue_split', 'create_issue_split_child_4'],
  'id': 'create_issue_split_child_5',
  'when': {'equals': 'present', 'path': 'child_5', 'upstream': 'plan_issue_split'}},
 {'conduction': ['get_issue',
                 'plan_issue_split',
                 'create_issue_split_child_1',
                 'create_issue_split_child_2',
                 'create_issue_split_child_3',
                 'create_issue_split_child_4',
                 'create_issue_split_child_5'],
  'id': 'mark_issue_tracker',
  'when': {'equals': 'children', 'path': 'route', 'upstream': 'plan_issue_split'}},
 {'conduction': ['get_issue',
                 'plan_issue_split',
                 'create_issue_split_child_1',
                 'create_issue_split_child_2',
                 'create_issue_split_child_3',
                 'create_issue_split_child_4',
                 'create_issue_split_child_5',
                 'mark_issue_tracker'],
  'id': 'comment_issue_tracker',
  'when': {'equals': 'children', 'path': 'route', 'upstream': 'plan_issue_split'}},
 {'conduction': ['get_issue', 'plan_issue_split', 'comment_issue_tracker'],
  'id': 'close_issue_tracker',
  'when': {'equals': 'children', 'path': 'route', 'upstream': 'plan_issue_split'}},
 {'conduction': ['plan_issue_split'],
  'id': 'select_park_stop',
  'when': {'equals': 'park', 'path': 'route', 'upstream': 'plan_issue_split'}},
 {'conduction': ['get_issue', 'plan_issue_split', 'select_park_stop'],
  'id': 'apply_issue_manual',
  'when': {'equals': 'skip', 'path': 'route', 'upstream': 'select_park_stop'}},
 {'conduction': ['plan_issue_split',
                 'comment_issue_tracker',
                 'close_issue_tracker',
                 'select_park_stop',
                 'apply_issue_manual'],
  'id': 'summarize_issue_split',
  'when': None}]
_MATCH = {'plan_issue_split': {'child_1': 'present',
                      'child_2': 'present',
                      'child_3': 'present',
                      'child_4': 'present',
                      'child_5': 'present',
                      'route': 'children'},
 'select_park_stop': {'route': 'skip'}}
_MISS = {'plan_issue_split': {'child_1': 'not-present',
                      'child_2': 'not-present',
                      'child_3': 'not-present',
                      'child_4': 'not-present',
                      'child_5': 'not-present',
                      'route': 'not-children'},
 'select_park_stop': {'route': 'not-skip'}}
_MAX_TICKS = 52

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
