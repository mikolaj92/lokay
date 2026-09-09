"""Native Fala host_run_package proofs for implementation_dispatch."""
from __future__ import annotations

import pytest

_PATH_ID = 'implementation_dispatch'
_EFFECTORS = [{'conduction': [], 'id': 'select_implementation_candidate', 'when': None},
 {'conduction': ['select_implementation_candidate'],
  'id': 'inspect_implementation_mutex',
  'when': {'equals': 'candidate', 'path': 'route', 'upstream': 'select_implementation_candidate'}},
 {'conduction': ['select_implementation_candidate', 'inspect_implementation_mutex'],
  'id': 'select_mutex_outcome',
  'when': None},
 {'conduction': ['select_mutex_outcome'],
  'id': 'keep_implementation_candidate',
  'when': {'equals': 'keep', 'path': 'route', 'upstream': 'select_mutex_outcome'}},
 {'conduction': ['select_mutex_outcome'],
  'id': 'verify_selected_issue_ready',
  'when': {'equals': 'free', 'path': 'route', 'upstream': 'select_mutex_outcome'}},
 {'conduction': ['select_mutex_outcome', 'verify_selected_issue_ready'],
  'id': 'select_ready_outcome',
  'when': None},
 {'conduction': ['select_ready_outcome'],
  'id': 'drop_stale_implementation_candidate',
  'when': {'equals': 'stale', 'path': 'route', 'upstream': 'select_ready_outcome'}},
 {'conduction': ['select_ready_outcome'],
  'id': 'launch_issue_to_pr',
  'when': {'equals': 'ready', 'path': 'route', 'upstream': 'select_ready_outcome'}},
 {'conduction': ['select_ready_outcome', 'launch_issue_to_pr'], 'id': 'select_launch_route', 'when': None},
 {'conduction': ['select_launch_route'],
  'id': 'record_dispatch_success',
  'when': {'equals': 'started', 'path': 'route', 'upstream': 'select_launch_route'}},
 {'conduction': ['select_launch_route'],
  'id': 'record_dispatch_failure',
  'when': {'equals': 'failed', 'path': 'route', 'upstream': 'select_launch_route'}},
 {'conduction': ['select_launch_route'],
  'id': 'keep_busy_launch',
  'when': {'equals': 'busy', 'path': 'route', 'upstream': 'select_launch_route'}},
 {'conduction': ['record_dispatch_success', 'record_dispatch_failure'],
  'id': 'select_dispatch_outcome',
  'when': None},
 {'conduction': ['select_dispatch_outcome'],
  'id': 'persist_dispatch_stuck',
  'when': {'equals': True, 'path': 'stuck_changed', 'upstream': 'select_dispatch_outcome'}},
 {'conduction': ['select_dispatch_outcome'],
  'id': 'label_blocked_dispatch',
  'when': {'equals': 'blocked', 'path': 'route', 'upstream': 'select_dispatch_outcome'}},
 {'conduction': ['label_blocked_dispatch'], 'id': 'persist_blocked_dispatch', 'when': None},
 {'conduction': ['persist_blocked_dispatch', 'select_dispatch_outcome'],
  'id': 'select_blocked_dispatch',
  'when': None},
 {'conduction': ['select_blocked_dispatch'],
  'id': 'park_plan_only_dispatch',
  'when': {'equals': 'park', 'path': 'route', 'upstream': 'select_blocked_dispatch'}},
 {'conduction': ['select_dispatch_outcome'],
  'id': 'write_dispatch_receipt',
  'when': {'equals': 'receipt', 'path': 'route', 'upstream': 'select_dispatch_outcome'}},
 {'conduction': ['select_implementation_candidate',
                 'inspect_implementation_mutex',
                 'select_mutex_outcome',
                 'keep_implementation_candidate',
                 'verify_selected_issue_ready',
                 'select_ready_outcome',
                 'drop_stale_implementation_candidate',
                 'launch_issue_to_pr',
                 'select_launch_route',
                 'keep_busy_launch',
                 'record_dispatch_success',
                 'record_dispatch_failure',
                 'select_dispatch_outcome',
                 'persist_dispatch_stuck',
                 'label_blocked_dispatch',
                 'persist_blocked_dispatch',
                 'select_blocked_dispatch',
                 'park_plan_only_dispatch',
                 'write_dispatch_receipt'],
  'id': 'summarize_implementation_dispatch',
  'when': None}]
_MATCH = {'select_blocked_dispatch': {'route': 'park'},
 'select_dispatch_outcome': {'route': 'blocked', 'stuck_changed': True},
 'select_implementation_candidate': {'route': 'candidate'},
 'select_launch_route': {'route': 'started'},
 'select_mutex_outcome': {'route': 'keep'},
 'select_ready_outcome': {'route': 'stale'}}
_MISS = {'select_blocked_dispatch': {'route': 'not-park'},
 'select_dispatch_outcome': {'route': 'not-blocked', 'stuck_changed': False},
 'select_implementation_candidate': {'route': 'not-candidate'},
 'select_launch_route': {'route': 'not-started'},
 'select_mutex_outcome': {'route': 'not-keep'},
 'select_ready_outcome': {'route': 'not-stale'}}
_MAX_TICKS = 80

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
