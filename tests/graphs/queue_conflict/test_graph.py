"""Native Fala host_run_package proofs for queue_conflict."""
from __future__ import annotations

import pytest

_PATH_ID = 'queue_conflict'
_EFFECTORS = [{'conduction': [], 'id': 'select_queue_conflict_candidate', 'when': None},
 {'conduction': ['select_queue_conflict_candidate'],
  'id': 'check_queue_covering_pr',
  'when': {'equals': 'candidate', 'path': 'route', 'upstream': 'select_queue_conflict_candidate'}},
 {'conduction': ['select_queue_conflict_candidate', 'check_queue_covering_pr'],
  'id': 'select_queue_conflict_gate',
  'when': None},
 {'conduction': ['select_queue_conflict_gate'],
  'id': 'queue_conflict_agent',
  'when': {'equals': 'agent', 'path': 'route', 'upstream': 'select_queue_conflict_gate'}},
 {'conduction': ['queue_conflict_agent'], 'id': 'validate_queue_conflict', 'when': None},
 {'conduction': ['validate_queue_conflict', 'select_queue_conflict_gate'],
  'id': 'queue_conflict_retry_agent',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_queue_conflict'}},
 {'conduction': ['queue_conflict_retry_agent'], 'id': 'validate_queue_conflict_retry', 'when': None},
 {'conduction': ['select_queue_conflict_candidate',
                 'select_queue_conflict_gate',
                 'validate_queue_conflict',
                 'validate_queue_conflict_retry'],
  'id': 'select_queue_conflict_outcome',
  'when': None},
 {'conduction': ['select_queue_conflict_outcome'],
  'id': 'remove_queue_ready_label',
  'when': {'equals': 'close', 'path': 'route', 'upstream': 'select_queue_conflict_outcome'}},
 {'conduction': ['select_queue_conflict_outcome', 'remove_queue_ready_label'],
  'id': 'select_queue_tracker',
  'when': None},
 {'conduction': ['select_queue_tracker'],
  'id': 'add_queue_tracker_label',
  'when': {'equals': 'tracker', 'path': 'route', 'upstream': 'select_queue_tracker'}},
 {'conduction': ['select_queue_conflict_outcome', 'remove_queue_ready_label', 'add_queue_tracker_label'],
  'id': 'record_queue_conflict',
  'when': None},
 {'conduction': ['record_queue_conflict'], 'id': 'advance_implementation_selection', 'when': None},
 {'conduction': ['select_queue_conflict_candidate',
                 'record_queue_conflict',
                 'advance_implementation_selection'],
  'id': 'summarize_queue_conflict',
  'when': None}]
_MATCH = {'select_queue_conflict_candidate': {'route': 'candidate'},
 'select_queue_conflict_gate': {'route': 'agent'},
 'select_queue_conflict_outcome': {'route': 'close'},
 'select_queue_tracker': {'route': 'tracker'},
 'validate_queue_conflict': {'route': 'retry'}}
_MISS = {'select_queue_conflict_candidate': {'route': 'not-candidate'},
 'select_queue_conflict_gate': {'route': 'not-agent'},
 'select_queue_conflict_outcome': {'route': 'not-close'},
 'select_queue_tracker': {'route': 'not-tracker'},
 'validate_queue_conflict': {'route': 'not-retry'}}
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
