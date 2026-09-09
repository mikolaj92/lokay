"""Native Fala host_run_package proofs for executor_rows."""
from __future__ import annotations

import pytest

_PATH_ID = 'executor_rows'
_EFFECTORS = [{'conduction': [], 'id': 'prepare_executor_rows', 'when': None},
 {'conduction': ['prepare_executor_rows'], 'id': 'select_executor_slot_1', 'when': None},
 {'conduction': ['prepare_executor_rows', 'select_executor_slot_1'],
  'id': 'run_executor_row_1',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_executor_slot_1'}},
 {'conduction': ['prepare_executor_rows', 'select_executor_slot_1', 'run_executor_row_1'],
  'id': 'classify_executor_row_1',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'classify_executor_row_1'],
  'id': 'select_executor_slot_2',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'select_executor_slot_2', 'classify_executor_row_1'],
  'id': 'run_executor_row_2',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_executor_slot_2'}},
 {'conduction': ['prepare_executor_rows',
                 'select_executor_slot_2',
                 'run_executor_row_2',
                 'classify_executor_row_1'],
  'id': 'classify_executor_row_2',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'classify_executor_row_2'],
  'id': 'select_executor_slot_3',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'select_executor_slot_3', 'classify_executor_row_2'],
  'id': 'run_executor_row_3',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_executor_slot_3'}},
 {'conduction': ['prepare_executor_rows',
                 'select_executor_slot_3',
                 'run_executor_row_3',
                 'classify_executor_row_2'],
  'id': 'classify_executor_row_3',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'classify_executor_row_3'],
  'id': 'select_executor_slot_4',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'select_executor_slot_4', 'classify_executor_row_3'],
  'id': 'run_executor_row_4',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_executor_slot_4'}},
 {'conduction': ['prepare_executor_rows',
                 'select_executor_slot_4',
                 'run_executor_row_4',
                 'classify_executor_row_3'],
  'id': 'classify_executor_row_4',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'classify_executor_row_4'],
  'id': 'select_executor_slot_5',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'select_executor_slot_5', 'classify_executor_row_4'],
  'id': 'run_executor_row_5',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_executor_slot_5'}},
 {'conduction': ['prepare_executor_rows',
                 'select_executor_slot_5',
                 'run_executor_row_5',
                 'classify_executor_row_4'],
  'id': 'classify_executor_row_5',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'classify_executor_row_5'],
  'id': 'select_executor_slot_6',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'select_executor_slot_6', 'classify_executor_row_5'],
  'id': 'run_executor_row_6',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_executor_slot_6'}},
 {'conduction': ['prepare_executor_rows',
                 'select_executor_slot_6',
                 'run_executor_row_6',
                 'classify_executor_row_5'],
  'id': 'classify_executor_row_6',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'classify_executor_row_6'],
  'id': 'select_executor_slot_7',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'select_executor_slot_7', 'classify_executor_row_6'],
  'id': 'run_executor_row_7',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_executor_slot_7'}},
 {'conduction': ['prepare_executor_rows',
                 'select_executor_slot_7',
                 'run_executor_row_7',
                 'classify_executor_row_6'],
  'id': 'classify_executor_row_7',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'classify_executor_row_7'],
  'id': 'select_executor_slot_8',
  'when': None},
 {'conduction': ['prepare_executor_rows', 'select_executor_slot_8', 'classify_executor_row_7'],
  'id': 'run_executor_row_8',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_executor_slot_8'}},
 {'conduction': ['prepare_executor_rows',
                 'select_executor_slot_8',
                 'run_executor_row_8',
                 'classify_executor_row_7'],
  'id': 'classify_executor_row_8',
  'when': None},
 {'conduction': ['prepare_executor_rows',
                 'classify_executor_row_1',
                 'classify_executor_row_2',
                 'classify_executor_row_3',
                 'classify_executor_row_4',
                 'classify_executor_row_5',
                 'classify_executor_row_6',
                 'classify_executor_row_7',
                 'classify_executor_row_8'],
  'id': 'select_executor_result',
  'when': None}]
_MATCH = {'select_executor_slot_1': {'route': 'run'},
 'select_executor_slot_2': {'route': 'run'},
 'select_executor_slot_3': {'route': 'run'},
 'select_executor_slot_4': {'route': 'run'},
 'select_executor_slot_5': {'route': 'run'},
 'select_executor_slot_6': {'route': 'run'},
 'select_executor_slot_7': {'route': 'run'},
 'select_executor_slot_8': {'route': 'run'}}
_MISS = {'select_executor_slot_1': {'route': 'not-run'},
 'select_executor_slot_2': {'route': 'not-run'},
 'select_executor_slot_3': {'route': 'not-run'},
 'select_executor_slot_4': {'route': 'not-run'},
 'select_executor_slot_5': {'route': 'not-run'},
 'select_executor_slot_6': {'route': 'not-run'},
 'select_executor_slot_7': {'route': 'not-run'},
 'select_executor_slot_8': {'route': 'not-run'}}
_MAX_TICKS = 104

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
