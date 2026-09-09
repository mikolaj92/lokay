"""Native Fala host_run_package proofs for assert_real_diff_execution."""
from __future__ import annotations

import pytest

_PATH_ID = 'assert_real_diff_execution'
_EFFECTORS = [{'conduction': [], 'id': 'inspect_real_diff_worktree', 'when': None},
 {'conduction': ['inspect_real_diff_worktree'], 'id': 'read_real_diff_paths', 'when': None},
 {'conduction': ['read_real_diff_paths'], 'id': 'classify_real_diff_kind', 'when': None},
 {'conduction': ['inspect_real_diff_worktree'], 'id': 'read_real_diff_localize_scope', 'when': None},
 {'conduction': [], 'id': 'read_real_diff_issue_scope', 'when': None},
 {'conduction': ['read_real_diff_paths', 'read_real_diff_issue_scope'],
  'id': 'classify_ticket_scope_presence',
  'when': None},
 {'conduction': ['read_real_diff_paths', 'read_real_diff_issue_scope', 'classify_ticket_scope_presence'],
  'id': 'classify_ticket_scope_extra',
  'when': None},
 {'conduction': ['read_real_diff_paths', 'read_real_diff_localize_scope', 'classify_ticket_scope_extra'],
  'id': 'classify_localized_diff_scope',
  'when': None},
 {'conduction': ['classify_real_diff_kind', 'classify_localized_diff_scope'],
  'id': 'classify_real_diff_progress',
  'when': None},
 {'conduction': ['inspect_real_diff_worktree',
                 'read_real_diff_paths',
                 'classify_real_diff_kind',
                 'read_real_diff_localize_scope',
                 'classify_ticket_scope_presence',
                 'classify_ticket_scope_extra',
                 'classify_localized_diff_scope',
                 'classify_real_diff_progress'],
  'id': 'real_diff_terminal',
  'when': None}]
_MATCH = {}
_MISS = {}
_MAX_TICKS = 40

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
