"""Native Fala host_run_package proofs for factory_pass."""
from __future__ import annotations

import pytest

_PATH_ID = 'factory_pass'
_EFFECTORS = [{'conduction': [], 'id': 'harvest_factory_children', 'when': None},
 {'conduction': ['harvest_factory_children'], 'id': 'host_ff', 'when': None},
 {'conduction': ['host_ff'], 'id': 'factory_begin_host_gate', 'when': None},
 {'conduction': ['factory_begin_host_gate'],
  'id': 'factory_begin',
  'when': {'equals': 'begin', 'path': 'route', 'upstream': 'factory_begin_host_gate'}},
 {'conduction': ['factory_begin_host_gate', 'factory_begin'],
  'id': 'select_self_repair_department',
  'when': None},
 {'conduction': ['select_self_repair_department'],
  'id': 'run_self_repair_department',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_self_repair_department'}},
 {'conduction': ['factory_begin_host_gate', 'factory_begin', 'select_self_repair_department'],
  'id': 'select_issue_triage_department',
  'when': None},
 {'conduction': ['select_issue_triage_department', 'factory_begin'],
  'id': 'run_issue_triage_department',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_issue_triage_department'}},
 {'conduction': ['factory_begin_host_gate',
                 'factory_begin',
                 'select_issue_triage_department',
                 'run_issue_triage_department'],
  'id': 'select_executor_department',
  'when': None},
 {'conduction': ['select_executor_department',
                 'factory_begin',
                 'run_issue_triage_department',
                 'select_issue_triage_department'],
  'id': 'run_executor_department',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_executor_department'}},
 {'conduction': ['factory_begin_host_gate', 'factory_begin', 'select_executor_department'],
  'id': 'select_pr_triage_department',
  'when': None},
 {'conduction': ['select_pr_triage_department'],
  'id': 'run_pr_triage_department',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_pr_triage_department'}},
 {'conduction': ['factory_begin_host_gate',
                 'factory_begin',
                 'select_pr_triage_department',
                 'run_pr_triage_department'],
  'id': 'select_pr_repair_department',
  'when': None},
 {'conduction': ['select_pr_repair_department'],
  'id': 'run_pr_repair_department',
  'when': {'equals': 'repair', 'path': 'route', 'upstream': 'select_pr_repair_department'}},
 {'conduction': ['factory_begin_host_gate',
                 'factory_begin',
                 'select_self_repair_department',
                 'select_issue_triage_department',
                 'select_executor_department',
                 'select_pr_triage_department',
                 'select_pr_repair_department',
                 'run_self_repair_department',
                 'run_issue_triage_department',
                 'run_executor_department',
                 'run_pr_triage_department',
                 'run_pr_repair_department'],
  'id': 'record_pass',
  'when': None},
 {'conduction': ['record_pass'], 'id': 'factory_pass_terminal', 'when': None},
 {'conduction': ['factory_begin_host_gate', 'factory_begin'], 'id': 'reap_stale_worktrees', 'when': None}]
_MATCH = {'factory_begin_host_gate': {'route': 'begin'},
 'select_executor_department': {'route': 'run'},
 'select_issue_triage_department': {'route': 'run'},
 'select_pr_repair_department': {'route': 'repair'},
 'select_pr_triage_department': {'route': 'run'},
 'select_self_repair_department': {'route': 'run'}}
_MISS = {'factory_begin_host_gate': {'route': 'not-begin'},
 'select_executor_department': {'route': 'not-run'},
 'select_issue_triage_department': {'route': 'not-run'},
 'select_pr_repair_department': {'route': 'not-repair'},
 'select_pr_triage_department': {'route': 'not-run'},
 'select_self_repair_department': {'route': 'not-run'}}
_MAX_TICKS = 68

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
