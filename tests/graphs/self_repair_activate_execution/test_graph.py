"""Native Fala host_run_package proofs for self_repair_activate_execution."""
from __future__ import annotations

import pytest

_PATH_ID = 'self_repair_activate_execution'
_EFFECTORS = [{'conduction': [], 'id': 'prepare_self_repair_activation', 'when': None},
 {'conduction': ['prepare_self_repair_activation'],
  'id': 'read_canonical_checkout_status',
  'when': {'equals': 'status', 'path': 'route', 'upstream': 'prepare_self_repair_activation'}},
 {'conduction': ['prepare_self_repair_activation', 'read_canonical_checkout_status'],
  'id': 'classify_canonical_checkout',
  'when': None},
 {'conduction': ['prepare_self_repair_activation', 'classify_canonical_checkout'],
  'id': 'check_dirty_commit_on_origin',
  'when': {'equals': 'dirty', 'path': 'route', 'upstream': 'classify_canonical_checkout'}},
 {'conduction': ['prepare_self_repair_activation', 'classify_canonical_checkout'],
  'id': 'fetch_canonical_main',
  'when': {'equals': 'clean', 'path': 'route', 'upstream': 'classify_canonical_checkout'}},
 {'conduction': ['classify_canonical_checkout', 'fetch_canonical_main'],
  'id': 'record_canonical_fetch',
  'when': None},
 {'conduction': ['prepare_self_repair_activation', 'record_canonical_fetch'],
  'id': 'fast_forward_recovery_commit',
  'when': {'equals': 'fetched', 'path': 'route', 'upstream': 'record_canonical_fetch'}},
 {'conduction': ['record_canonical_fetch', 'fast_forward_recovery_commit'],
  'id': 'record_recovery_fast_forward',
  'when': None},
 {'conduction': ['prepare_self_repair_activation', 'record_recovery_fast_forward'],
  'id': 'read_activated_head',
  'when': {'equals': 'merged', 'path': 'route', 'upstream': 'record_recovery_fast_forward'}},
 {'conduction': ['prepare_self_repair_activation',
                 'classify_canonical_checkout',
                 'check_dirty_commit_on_origin',
                 'record_canonical_fetch',
                 'record_recovery_fast_forward',
                 'read_activated_head'],
  'id': 'classify_activated_head',
  'when': None},
 {'conduction': ['prepare_self_repair_activation', 'classify_activated_head'],
  'id': 'check_recovery_ancestor_head',
  'when': {'equals': 'ancestry', 'path': 'route', 'upstream': 'classify_activated_head'}},
 {'conduction': ['classify_activated_head', 'check_recovery_ancestor_head'],
  'id': 'record_recovery_head_ancestry',
  'when': None},
 {'conduction': ['prepare_self_repair_activation',
                 'classify_activated_head',
                 'record_recovery_head_ancestry'],
  'id': 'check_recovery_ancestor_origin',
  'when': {'equals': 'not_ancestor', 'path': 'route', 'upstream': 'record_recovery_head_ancestry'}},
 {'conduction': ['prepare_self_repair_activation',
                 'classify_canonical_checkout',
                 'check_dirty_commit_on_origin',
                 'record_canonical_fetch',
                 'record_recovery_fast_forward',
                 'read_activated_head',
                 'classify_activated_head',
                 'record_recovery_head_ancestry',
                 'check_recovery_ancestor_origin'],
  'id': 'self_repair_activation_terminal',
  'when': None}]
_MATCH = {'classify_activated_head': {'route': 'ancestry'},
 'classify_canonical_checkout': {'route': 'dirty'},
 'prepare_self_repair_activation': {'route': 'status'},
 'record_canonical_fetch': {'route': 'fetched'},
 'record_recovery_fast_forward': {'route': 'merged'},
 'record_recovery_head_ancestry': {'route': 'not_ancestor'}}
_MISS = {'classify_activated_head': {'route': 'not-ancestry'},
 'classify_canonical_checkout': {'route': 'not-dirty'},
 'prepare_self_repair_activation': {'route': 'not-status'},
 'record_canonical_fetch': {'route': 'not-fetched'},
 'record_recovery_fast_forward': {'route': 'not-merged'},
 'record_recovery_head_ancestry': {'route': 'not-not_ancestor'}}
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
