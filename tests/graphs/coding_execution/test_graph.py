"""Native Fala host_run_package proofs for coding_execution."""
from __future__ import annotations

import pytest

_PATH_ID = 'coding_execution'
_EFFECTORS = [{'conduction': [], 'id': 'prepare_coding_request', 'when': None},
 {'conduction': ['prepare_coding_request'], 'id': 'run_agent', 'when': None},
 {'conduction': ['run_agent'], 'id': 'validate_coding_result', 'when': None},
 {'conduction': ['prepare_coding_request', 'validate_coding_result'],
  'id': 'coding_retry_agent',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_coding_result'}},
 {'conduction': ['validate_coding_result', 'coding_retry_agent'],
  'id': 'validate_coding_retry',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_coding_result'}},
 {'conduction': ['validate_coding_result', 'validate_coding_retry'],
  'id': 'select_coding_result',
  'when': None},
 {'conduction': ['prepare_coding_request', 'select_coding_result'],
  'id': 'collect_coding_issue_snapshot',
  'when': {'equals': 'issue_snapshot', 'path': 'evidence_kind', 'upstream': 'select_coding_result'}},
 {'conduction': ['prepare_coding_request', 'select_coding_result'],
  'id': 'collect_coding_repo_structure',
  'when': {'equals': 'repo_structure', 'path': 'evidence_kind', 'upstream': 'select_coding_result'}},
 {'conduction': ['prepare_coding_request', 'select_coding_result'],
  'id': 'collect_coding_test_contract',
  'when': {'equals': 'test_contract', 'path': 'evidence_kind', 'upstream': 'select_coding_result'}},
 {'conduction': ['prepare_coding_request', 'select_coding_result'],
  'id': 'collect_coding_localized_diff',
  'when': {'equals': 'localized_diff', 'path': 'evidence_kind', 'upstream': 'select_coding_result'}},
 {'conduction': ['prepare_coding_request',
                 'select_coding_result',
                 'collect_coding_issue_snapshot',
                 'collect_coding_repo_structure',
                 'collect_coding_test_contract',
                 'collect_coding_localized_diff'],
  'id': 'evidence_coding_agent',
  'when': {'equals': 'evidence', 'path': 'route', 'upstream': 'select_coding_result'}},
 {'conduction': ['select_coding_result', 'evidence_coding_agent'],
  'id': 'validate_evidence_coding',
  'when': {'equals': 'evidence', 'path': 'route', 'upstream': 'select_coding_result'}},
 {'conduction': ['select_coding_result', 'validate_evidence_coding'],
  'id': 'select_evidence_coding',
  'when': None},
 {'conduction': ['select_coding_result', 'select_evidence_coding'],
  'id': 'finalize_coding_result',
  'when': None},
 {'conduction': ['finalize_coding_result'],
  'id': 'coding_fail_closed',
  'when': {'equals': 'fail_closed', 'path': 'route', 'upstream': 'finalize_coding_result'}},
 {'conduction': ['finalize_coding_result', 'coding_fail_closed'],
  'id': 'coding_execution_terminal',
  'when': None}]
_MATCH = {'finalize_coding_result': {'route': 'fail_closed'},
 'select_coding_result': {'evidence_kind': 'issue_snapshot', 'route': 'evidence'},
 'validate_coding_result': {'route': 'retry'}}
_MISS = {'finalize_coding_result': {'route': 'not-fail_closed'},
 'select_coding_result': {'evidence_kind': 'not-issue_snapshot', 'route': 'not-evidence'},
 'validate_coding_result': {'route': 'not-retry'}}
_MAX_TICKS = 64

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
