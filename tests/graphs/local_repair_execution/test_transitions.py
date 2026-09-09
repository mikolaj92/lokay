"""Independent conduction and when metadata for local_repair_execution."""
from __future__ import annotations
import json

_PATH_ID = 'local_repair_execution'
_NODES = {'assert_repair_diff': {'atom': 'assert_real_diff',
                        'conduction': ['prepare_local_repair_request', 'select_repair_result'],
                        'when': {'equals': 'repaired', 'path': 'route', 'upstream': 'select_repair_result'}},
 'commit_repair': {'atom': 'commit_all',
                   'conduction': ['prepare_local_repair_request',
                                  'select_repair_result',
                                  'assert_repair_diff'],
                   'when': {'equals': 'repaired', 'path': 'route', 'upstream': 'select_repair_result'}},
 'local_repair_retry_agent': {'atom': 'local_repair_retry_agent',
                              'conduction': ['prepare_local_repair_request', 'validate_repair_result'],
                              'when': {'equals': 'retry',
                                       'path': 'route',
                                       'upstream': 'validate_repair_result'}},
 'local_repair_terminal': {'atom': 'local_repair_terminal',
                           'conduction': ['select_repair_result', 'select_local_test_recheck'],
                           'when': None},
 'prepare_local_repair_request': {'atom': 'prepare_local_repair_request', 'conduction': [], 'when': None},
 'repair_agent': {'atom': 'repair_agent', 'conduction': ['prepare_local_repair_request'], 'when': None},
 'select_local_test_recheck': {'atom': 'select_local_test_recheck',
                               'conduction': ['test_local_recheck', 'select_repair_result'],
                               'when': None},
 'select_repair_result': {'atom': 'select_repair_result',
                          'conduction': ['validate_repair_result', 'validate_local_repair_retry'],
                          'when': None},
 'test_local_recheck': {'atom': 'test_local',
                        'conduction': ['prepare_local_repair_request',
                                       'commit_repair',
                                       'repair_agent',
                                       'local_repair_retry_agent',
                                       'select_repair_result'],
                        'when': {'equals': 'repaired', 'path': 'route', 'upstream': 'select_repair_result'}},
 'validate_local_repair_retry': {'atom': 'validate_local_repair_retry',
                                 'conduction': ['validate_repair_result', 'local_repair_retry_agent'],
                                 'when': {'equals': 'retry',
                                          'path': 'route',
                                          'upstream': 'validate_repair_result'}},
 'validate_repair_result': {'atom': 'validate_repair_result',
                            'conduction': ['repair_agent', 'prepare_local_repair_request'],
                            'when': None}}
_COND_EDGES = [('prepare_local_repair_request', 'repair_agent'),
 ('repair_agent', 'validate_repair_result'),
 ('prepare_local_repair_request', 'validate_repair_result'),
 ('prepare_local_repair_request', 'local_repair_retry_agent'),
 ('validate_repair_result', 'local_repair_retry_agent'),
 ('validate_repair_result', 'validate_local_repair_retry'),
 ('local_repair_retry_agent', 'validate_local_repair_retry'),
 ('validate_repair_result', 'select_repair_result'),
 ('validate_local_repair_retry', 'select_repair_result'),
 ('prepare_local_repair_request', 'assert_repair_diff'),
 ('select_repair_result', 'assert_repair_diff'),
 ('prepare_local_repair_request', 'commit_repair'),
 ('select_repair_result', 'commit_repair'),
 ('assert_repair_diff', 'commit_repair'),
 ('prepare_local_repair_request', 'test_local_recheck'),
 ('commit_repair', 'test_local_recheck'),
 ('repair_agent', 'test_local_recheck'),
 ('local_repair_retry_agent', 'test_local_recheck'),
 ('select_repair_result', 'test_local_recheck'),
 ('test_local_recheck', 'select_local_test_recheck'),
 ('select_repair_result', 'select_local_test_recheck'),
 ('select_repair_result', 'local_repair_terminal'),
 ('select_local_test_recheck', 'local_repair_terminal')]
_WHEN_BRANCHES = [('local_repair_retry_agent', {'equals': 'retry', 'path': 'route', 'upstream': 'validate_repair_result'}),
 ('validate_local_repair_retry', {'equals': 'retry', 'path': 'route', 'upstream': 'validate_repair_result'}),
 ('assert_repair_diff', {'equals': 'repaired', 'path': 'route', 'upstream': 'select_repair_result'}),
 ('commit_repair', {'equals': 'repaired', 'path': 'route', 'upstream': 'select_repair_result'}),
 ('test_local_recheck', {'equals': 'repaired', 'path': 'route', 'upstream': 'select_repair_result'})]
_EFFECTORS = [{'conduction': [], 'id': 'prepare_local_repair_request', 'when': None},
 {'conduction': ['prepare_local_repair_request'], 'id': 'repair_agent', 'when': None},
 {'conduction': ['repair_agent', 'prepare_local_repair_request'],
  'id': 'validate_repair_result',
  'when': None},
 {'conduction': ['prepare_local_repair_request', 'validate_repair_result'],
  'id': 'local_repair_retry_agent',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_repair_result'}},
 {'conduction': ['validate_repair_result', 'local_repair_retry_agent'],
  'id': 'validate_local_repair_retry',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_repair_result'}},
 {'conduction': ['validate_repair_result', 'validate_local_repair_retry'],
  'id': 'select_repair_result',
  'when': None},
 {'conduction': ['prepare_local_repair_request', 'select_repair_result'],
  'id': 'assert_repair_diff',
  'when': {'equals': 'repaired', 'path': 'route', 'upstream': 'select_repair_result'}},
 {'conduction': ['prepare_local_repair_request', 'select_repair_result', 'assert_repair_diff'],
  'id': 'commit_repair',
  'when': {'equals': 'repaired', 'path': 'route', 'upstream': 'select_repair_result'}},
 {'conduction': ['prepare_local_repair_request',
                 'commit_repair',
                 'repair_agent',
                 'local_repair_retry_agent',
                 'select_repair_result'],
  'id': 'test_local_recheck',
  'when': {'equals': 'repaired', 'path': 'route', 'upstream': 'select_repair_result'}},
 {'conduction': ['test_local_recheck', 'select_repair_result'],
  'id': 'select_local_test_recheck',
  'when': None},
 {'conduction': ['select_repair_result', 'select_local_test_recheck'],
  'id': 'local_repair_terminal',
  'when': None}]

def test_every_conduction_edge_is_declared():
    got = {(str(up), nid) for nid, meta in _NODES.items() for up in meta["conduction"]}
    assert got == set(tuple(edge) for edge in _COND_EDGES)

def test_every_when_branch_is_declared():
    got = {(nid, json.dumps(meta["when"], sort_keys=True)) for nid, meta in _NODES.items() if meta["when"]}
    want = {(nid, json.dumps(when, sort_keys=True)) for nid, when in _WHEN_BRANCHES}
    assert got == want

def test_when_upstream_is_a_direct_parent():
    for nid, when in _WHEN_BRANCHES:
        assert when["upstream"] in _NODES[nid]["conduction"]

def test_unconditional_nodes_succeed_without_outputs():
    from support.graph_model import run_model
    status = run_model(_EFFECTORS, {})
    for nid, meta in _NODES.items():
        if meta["when"] is None:
            assert status[nid] == "succeeded"

