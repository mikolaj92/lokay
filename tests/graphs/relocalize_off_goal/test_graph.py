"""Native Fala host_run_package proofs for relocalize_off_goal."""
from __future__ import annotations

import pytest

_PATH_ID = 'relocalize_off_goal'
_EFFECTORS = [{'conduction': [], 'id': 'inspect_relocalization_evidence', 'when': None},
 {'conduction': ['inspect_relocalization_evidence'], 'id': 'read_relocalization_changed_paths', 'when': None},
 {'conduction': [], 'id': 'read_relocalization_issue_paths', 'when': None},
 {'conduction': ['read_relocalization_changed_paths', 'read_relocalization_issue_paths'],
  'id': 'classify_relocalization_residue',
  'when': None},
 {'conduction': ['classify_relocalization_residue'], 'id': 'authorize_relocalization_restore', 'when': None},
 {'conduction': ['inspect_relocalization_evidence',
                 'read_relocalization_changed_paths',
                 'authorize_relocalization_restore'],
  'id': 'restore_relocalization_residue',
  'when': {'equals': 'restore', 'path': 'route', 'upstream': 'authorize_relocalization_restore'}},
 {'conduction': ['classify_relocalization_residue',
                 'authorize_relocalization_restore',
                 'restore_relocalization_residue'],
  'id': 'record_relocalization_restore',
  'when': None},
 {'conduction': ['inspect_relocalization_evidence',
                 'read_relocalization_changed_paths',
                 'record_relocalization_restore'],
  'id': 'classify_relocalization_off_goal',
  'when': None},
 {'conduction': ['inspect_relocalization_evidence', 'classify_relocalization_off_goal'],
  'id': 'build_relocalization_agent_request',
  'when': None},
 {'conduction': ['inspect_relocalization_evidence', 'build_relocalization_agent_request'],
  'id': 'run_relocalization_agent',
  'when': {'equals': 'agent', 'path': 'route', 'upstream': 'build_relocalization_agent_request'}},
 {'conduction': ['run_relocalization_agent'], 'id': 'validate_relocalization_agent_json', 'when': None},
 {'conduction': ['validate_relocalization_agent_json'], 'id': 'build_relocalization_retry', 'when': None},
 {'conduction': ['inspect_relocalization_evidence',
                 'build_relocalization_agent_request',
                 'build_relocalization_retry'],
  'id': 'retry_relocalization_agent',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'build_relocalization_retry'}},
 {'conduction': ['retry_relocalization_agent'], 'id': 'validate_relocalization_retry_json', 'when': None},
 {'conduction': ['run_relocalization_agent',
                 'validate_relocalization_agent_json',
                 'retry_relocalization_agent',
                 'validate_relocalization_retry_json'],
  'id': 'select_relocalization_validation',
  'when': None},
 {'conduction': ['classify_relocalization_off_goal', 'select_relocalization_validation'],
  'id': 'validate_relocalization_approval',
  'when': None},
 {'conduction': ['inspect_relocalization_evidence',
                 'classify_relocalization_off_goal',
                 'validate_relocalization_approval'],
  'id': 'write_relocalization_evidence',
  'when': {'equals': 'write', 'path': 'route', 'upstream': 'validate_relocalization_approval'}},
 {'conduction': ['inspect_relocalization_evidence',
                 'read_relocalization_changed_paths',
                 'classify_relocalization_off_goal',
                 'validate_relocalization_approval',
                 'write_relocalization_evidence'],
  'id': 'relocalization_terminal',
  'when': None}]
_MATCH = {'authorize_relocalization_restore': {'route': 'restore'},
 'build_relocalization_agent_request': {'route': 'agent'},
 'build_relocalization_retry': {'route': 'retry'},
 'validate_relocalization_approval': {'route': 'write'}}
_MISS = {'authorize_relocalization_restore': {'route': 'not-restore'},
 'build_relocalization_agent_request': {'route': 'not-agent'},
 'build_relocalization_retry': {'route': 'not-retry'},
 'validate_relocalization_approval': {'route': 'not-write'}}
_MAX_TICKS = 72

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
