"""Native Fala host_run_package proofs for closeout_pr."""
from __future__ import annotations

import pytest

_PATH_ID = 'closeout_pr'
_EFFECTORS = [{'conduction': [], 'id': 'inspect_closeout_pr', 'when': None},
 {'conduction': ['inspect_closeout_pr'], 'id': 'read_closeout_issue', 'when': None},
 {'conduction': ['inspect_closeout_pr', 'read_closeout_issue'], 'id': 'classify_closeout_gate', 'when': None},
 {'conduction': ['classify_closeout_gate'],
  'id': 'park_closed_pr_issue',
  'when': {'equals': 'issue_closed', 'path': 'route', 'upstream': 'classify_closeout_gate'}},
 {'conduction': ['classify_closeout_gate'],
  'id': 'read_closeout_checks',
  'when': {'equals': 'checks', 'path': 'route', 'upstream': 'classify_closeout_gate'}},
 {'conduction': ['classify_closeout_gate', 'read_closeout_checks'],
  'id': 'route_closeout_checks',
  'when': None},
 {'conduction': ['classify_closeout_gate', 'route_closeout_checks'],
  'id': 'authorize_closeout_repair',
  'when': None},
 {'conduction': ['classify_closeout_gate', 'authorize_closeout_repair'],
  'id': 'run_closeout_repair',
  'when': {'equals': 'repair', 'path': 'route', 'upstream': 'authorize_closeout_repair'}},
 {'conduction': ['classify_closeout_gate', 'route_closeout_checks'],
  'id': 'run_closeout_triage',
  'when': {'equals': 'triage', 'path': 'route', 'upstream': 'route_closeout_checks'}},
 {'conduction': ['route_closeout_checks', 'run_closeout_triage'],
  'id': 'classify_closeout_triage',
  'when': None},
 {'conduction': ['classify_closeout_gate', 'classify_closeout_triage'],
  'id': 'authorize_closeout_review_repair',
  'when': None},
 {'conduction': ['classify_closeout_gate', 'authorize_closeout_review_repair'],
  'id': 'run_closeout_review_repair',
  'when': {'equals': 'repair', 'path': 'route', 'upstream': 'authorize_closeout_review_repair'}},
 {'conduction': ['classify_closeout_gate', 'classify_closeout_triage'],
  'id': 'park_delivered_pr_issue',
  'when': {'equals': 'merged', 'path': 'route', 'upstream': 'classify_closeout_triage'}},
 {'conduction': ['authorize_closeout_repair',
                 'run_closeout_repair',
                 'authorize_closeout_review_repair',
                 'run_closeout_review_repair'],
  'id': 'select_closeout_repair_result',
  'when': None},
 {'conduction': ['park_closed_pr_issue', 'park_delivered_pr_issue'],
  'id': 'select_closeout_park_result',
  'when': None},
 {'conduction': ['classify_closeout_gate',
                 'route_closeout_checks',
                 'classify_closeout_triage',
                 'select_closeout_repair_result',
                 'select_closeout_park_result'],
  'id': 'build_closeout_evidence',
  'when': None},
 {'conduction': ['classify_closeout_gate',
                 'route_closeout_checks',
                 'classify_closeout_triage',
                 'select_closeout_repair_result',
                 'build_closeout_evidence'],
  'id': 'finalize_closeout_pr',
  'when': None},
 {'conduction': ['finalize_closeout_pr'], 'id': 'summarize_closeout_pr', 'when': None}]
_MATCH = {'authorize_closeout_repair': {'route': 'repair'},
 'authorize_closeout_review_repair': {'route': 'repair'},
 'classify_closeout_gate': {'route': 'issue_closed'},
 'classify_closeout_triage': {'route': 'merged'},
 'route_closeout_checks': {'route': 'triage'}}
_MISS = {'authorize_closeout_repair': {'route': 'not-repair'},
 'authorize_closeout_review_repair': {'route': 'not-repair'},
 'classify_closeout_gate': {'route': 'not-issue_closed'},
 'classify_closeout_triage': {'route': 'not-merged'},
 'route_closeout_checks': {'route': 'not-triage'}}
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
