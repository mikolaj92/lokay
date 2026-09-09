"""Native Fala host_run_package proofs for issue_to_pr."""
from __future__ import annotations

import pytest

_PATH_ID = 'issue_to_pr'
_EFFECTORS = [{'conduction': [], 'id': 'get_issue', 'when': None},
 {'conduction': ['get_issue'], 'id': 'resolve_implementation_issue', 'when': None},
 {'conduction': ['get_issue', 'resolve_implementation_issue'],
  'id': 'collect_existing_delivery_pr',
  'when': None},
 {'conduction': ['get_issue', 'resolve_implementation_issue'], 'id': 'collect_resumed_source', 'when': None},
 {'conduction': ['resolve_implementation_issue', 'collect_existing_delivery_pr', 'collect_resumed_source'],
  'id': 'resolve_existing_delivery',
  'when': None},
 {'conduction': ['get_issue', 'resolve_existing_delivery'],
  'id': 'issue_to_pr_subflow',
  'when': {'equals': 'deliver', 'path': 'route', 'upstream': 'resolve_existing_delivery'}},
 {'conduction': ['get_issue', 'resolve_existing_delivery'],
  'id': 'close_existing_delivery',
  'when': {'equals': 'closeout', 'path': 'route', 'upstream': 'resolve_existing_delivery'}},
 {'conduction': ['resolve_existing_delivery'],
  'id': 'issue_to_pr_no_effect',
  'when': {'equals': 'no_effect', 'path': 'route', 'upstream': 'resolve_existing_delivery'}},
 {'conduction': ['resolve_existing_delivery',
                 'issue_to_pr_subflow',
                 'close_existing_delivery',
                 'issue_to_pr_no_effect'],
  'id': 'summarize_issue_to_pr',
  'when': None}]
_MATCH = {'resolve_existing_delivery': {'route': 'deliver'}}
_MISS = {'resolve_existing_delivery': {'route': 'not-deliver'}}
_MAX_TICKS = 36

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
