"""Native Fala host_run_package proofs for child_harvest."""
from __future__ import annotations

import pytest

_PATH_ID = 'child_harvest'
_EFFECTORS = [{'conduction': [], 'id': 'collect_child_harvest_facts', 'when': None},
 {'conduction': ['collect_child_harvest_facts'], 'id': 'reconcile_dead_child_receipts', 'when': None},
 {'conduction': ['reconcile_dead_child_receipts'], 'id': 'reconcile_harvest_journal_misses', 'when': None},
 {'conduction': ['reconcile_harvest_journal_misses'], 'id': 'reconcile_harvest_deliveries', 'when': None},
 {'conduction': ['reconcile_harvest_deliveries'], 'id': 'reconcile_harvest_blocked_misses', 'when': None},
 {'conduction': ['reconcile_harvest_blocked_misses'], 'id': 'harvest_catalog', 'when': None},
 {'conduction': ['harvest_catalog'], 'id': 'clear_harvest_closed_rows', 'when': None},
 {'conduction': ['clear_harvest_closed_rows'], 'id': 'drop_harvest_out_of_scope', 'when': None},
 {'conduction': ['drop_harvest_out_of_scope'], 'id': 'clear_harvest_cycle_starts', 'when': None},
 {'conduction': ['clear_harvest_cycle_starts'], 'id': 'child_harvest_terminal', 'when': None}]
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
