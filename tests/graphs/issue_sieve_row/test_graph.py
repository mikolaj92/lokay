"""Native Fala host_run_package proofs for issue_sieve_row."""
from __future__ import annotations

import pytest

_PATH_ID = 'issue_sieve_row'
_EFFECTORS = [{'conduction': [], 'id': 'select_next_issue', 'when': None},
 {'conduction': ['select_next_issue'],
  'id': 'issues_run_triage',
  'when': {'equals': 'issue', 'path': 'route', 'upstream': 'select_next_issue'}},
 {'conduction': ['select_next_issue', 'issues_run_triage'], 'id': 'select_issue_sieve', 'when': None},
 {'conduction': ['select_issue_sieve'],
  'id': 'run_issue_sieve_split',
  'when': {'equals': 'split', 'path': 'route', 'upstream': 'select_issue_sieve'}},
 {'conduction': ['select_next_issue', 'issues_run_triage', 'select_issue_sieve', 'run_issue_sieve_split'],
  'id': 'summarize_issue_sieve_row',
  'when': None}]
_MATCH = {'select_issue_sieve': {'route': 'split'}, 'select_next_issue': {'route': 'issue'}}
_MISS = {'select_issue_sieve': {'route': 'not-split'}, 'select_next_issue': {'route': 'not-issue'}}
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
