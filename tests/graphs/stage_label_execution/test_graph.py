"""Native Fala host_run_package proofs for stage_label_execution."""
from __future__ import annotations

import pytest

_PATH_ID = 'stage_label_execution'
_EFFECTORS = [{'conduction': [], 'id': 'prepare_stage_transition', 'when': None},
 {'conduction': ['prepare_stage_transition'], 'id': 'read_stage_issue', 'when': None},
 {'conduction': ['prepare_stage_transition', 'read_stage_issue'], 'id': 'classify_stage_issue', 'when': None},
 {'conduction': ['prepare_stage_transition', 'classify_stage_issue'],
  'id': 'remove_stage_labels_effect',
  'when': {'equals': 'remove', 'path': 'route', 'upstream': 'classify_stage_issue'}},
 {'conduction': ['classify_stage_issue', 'remove_stage_labels_effect'],
  'id': 'record_stage_removal',
  'when': None},
 {'conduction': ['prepare_stage_transition', 'record_stage_removal'],
  'id': 'add_stage_labels_effect',
  'when': None},
 {'conduction': ['prepare_stage_transition', 'add_stage_labels_effect'],
  'id': 'comment_stage_receipt_effect',
  'when': {'equals': 'comment', 'path': 'route', 'upstream': 'add_stage_labels_effect'}},
 {'conduction': ['prepare_stage_transition',
                 'read_stage_issue',
                 'classify_stage_issue',
                 'record_stage_removal',
                 'add_stage_labels_effect',
                 'comment_stage_receipt_effect'],
  'id': 'stage_label_terminal',
  'when': None}]
_MATCH = {'add_stage_labels_effect': {'route': 'comment'}, 'classify_stage_issue': {'route': 'remove'}}
_MISS = {'add_stage_labels_effect': {'route': 'not-comment'}, 'classify_stage_issue': {'route': 'not-remove'}}
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
