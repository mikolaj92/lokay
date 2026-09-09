"""Native Fala host_run_package proofs for localize_execution."""
from __future__ import annotations

import pytest

_PATH_ID = 'localize_execution'
_EFFECTORS = [{'conduction': [], 'id': 'prepare_localization_request', 'when': None},
 {'conduction': ['prepare_localization_request'], 'id': 'inspect_existing_localization', 'when': None},
 {'conduction': ['prepare_localization_request', 'inspect_existing_localization'],
  'id': 'classify_localization_route',
  'when': None},
 {'conduction': ['prepare_localization_request',
                 'inspect_existing_localization',
                 'classify_localization_route'],
  'id': 'build_explicit_localization',
  'when': None},
 {'conduction': ['prepare_localization_request'], 'id': 'build_deterministic_localization', 'when': None},
 {'conduction': ['prepare_localization_request',
                 'inspect_existing_localization',
                 'classify_localization_route'],
  'id': 'build_localization_agent_request',
  'when': None},
 {'conduction': ['prepare_localization_request', 'build_localization_agent_request'],
  'id': 'run_localization_agent',
  'when': {'equals': 'agent', 'path': 'route', 'upstream': 'build_localization_agent_request'}},
 {'conduction': ['run_localization_agent'], 'id': 'validate_localization_agent_json', 'when': None},
 {'conduction': ['validate_localization_agent_json'], 'id': 'build_localization_retry', 'when': None},
 {'conduction': ['prepare_localization_request',
                 'build_localization_agent_request',
                 'build_localization_retry'],
  'id': 'retry_localization_agent',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'build_localization_retry'}},
 {'conduction': ['retry_localization_agent'], 'id': 'validate_localization_retry_json', 'when': None},
 {'conduction': ['classify_localization_route',
                 'build_explicit_localization',
                 'build_deterministic_localization',
                 'run_localization_agent',
                 'validate_localization_agent_json',
                 'retry_localization_agent',
                 'validate_localization_retry_json'],
  'id': 'select_localization_candidate',
  'when': None},
 {'conduction': ['prepare_localization_request',
                 'inspect_existing_localization',
                 'build_localization_agent_request',
                 'select_localization_candidate'],
  'id': 'validate_localization_paths',
  'when': None},
 {'conduction': ['prepare_localization_request', 'validate_localization_paths'],
  'id': 'write_localization_evidence',
  'when': None},
 {'conduction': ['select_localization_candidate', 'write_localization_evidence'],
  'id': 'localization_terminal',
  'when': None}]
_MATCH = {'build_localization_agent_request': {'route': 'agent'}, 'build_localization_retry': {'route': 'retry'}}
_MISS = {'build_localization_agent_request': {'route': 'not-agent'},
 'build_localization_retry': {'route': 'not-retry'}}
_MAX_TICKS = 60

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
