"""Independent conduction and when metadata for self_repair_entry."""
from __future__ import annotations
import json

_PATH_ID = 'self_repair_entry'
_NODES = {'classify_self_repair_entry': {'atom': 'classify_self_repair_entry',
                                'conduction': ['prepare_self_repair_entry'],
                                'when': None},
 'classify_self_repair_entry_outcome': {'atom': 'classify_self_repair_entry_outcome',
                                        'conduction': ['record_authored_self_repair'],
                                        'when': None},
 'prepare_self_repair_entry': {'atom': 'prepare_self_repair_entry', 'conduction': [], 'when': None},
 'record_authored_self_repair': {'atom': 'record_authored_self_repair',
                                 'conduction': ['classify_self_repair_entry', 'run_authored_self_repair'],
                                 'when': None},
 'record_self_repair_entry_failure': {'atom': 'record_self_repair_entry_failure',
                                      'conduction': ['prepare_self_repair_entry',
                                                     'select_self_repair_entry_result'],
                                      'when': {'equals': 'failure',
                                               'path': 'route',
                                               'upstream': 'select_self_repair_entry_result'}},
 'record_self_repair_entry_start': {'atom': 'record_self_repair_entry_start',
                                    'conduction': ['prepare_self_repair_entry', 'classify_self_repair_entry'],
                                    'when': {'equals': 'run',
                                             'path': 'route',
                                             'upstream': 'classify_self_repair_entry'}},
 'record_self_repair_entry_success': {'atom': 'record_self_repair_entry_success',
                                      'conduction': ['prepare_self_repair_entry',
                                                     'select_self_repair_entry_result'],
                                      'when': {'equals': 'success',
                                               'path': 'route',
                                               'upstream': 'select_self_repair_entry_result'}},
 'run_authored_self_repair': {'atom': 'run_authored_self_repair',
                              'conduction': ['prepare_self_repair_entry',
                                             'classify_self_repair_entry',
                                             'record_self_repair_entry_start'],
                              'when': {'equals': 'run',
                                       'path': 'route',
                                       'upstream': 'classify_self_repair_entry'}},
 'select_self_repair_entry_result': {'atom': 'select_self_repair_entry_result',
                                     'conduction': ['prepare_self_repair_entry',
                                                    'classify_self_repair_entry',
                                                    'classify_self_repair_entry_outcome',
                                                    'write_self_repair_restart_marker'],
                                     'when': None},
 'self_repair_entry_terminal': {'atom': 'self_repair_entry_terminal',
                                'conduction': ['select_self_repair_entry_result',
                                               'record_self_repair_entry_success',
                                               'record_self_repair_entry_failure'],
                                'when': None},
 'write_self_repair_restart_marker': {'atom': 'write_self_repair_restart_marker',
                                      'conduction': ['prepare_self_repair_entry',
                                                     'classify_self_repair_entry_outcome'],
                                      'when': {'equals': 'restart',
                                               'path': 'route',
                                               'upstream': 'classify_self_repair_entry_outcome'}}}
_COND_EDGES = [('prepare_self_repair_entry', 'classify_self_repair_entry'),
 ('prepare_self_repair_entry', 'record_self_repair_entry_start'),
 ('classify_self_repair_entry', 'record_self_repair_entry_start'),
 ('prepare_self_repair_entry', 'run_authored_self_repair'),
 ('classify_self_repair_entry', 'run_authored_self_repair'),
 ('record_self_repair_entry_start', 'run_authored_self_repair'),
 ('classify_self_repair_entry', 'record_authored_self_repair'),
 ('run_authored_self_repair', 'record_authored_self_repair'),
 ('record_authored_self_repair', 'classify_self_repair_entry_outcome'),
 ('prepare_self_repair_entry', 'write_self_repair_restart_marker'),
 ('classify_self_repair_entry_outcome', 'write_self_repair_restart_marker'),
 ('prepare_self_repair_entry', 'select_self_repair_entry_result'),
 ('classify_self_repair_entry', 'select_self_repair_entry_result'),
 ('classify_self_repair_entry_outcome', 'select_self_repair_entry_result'),
 ('write_self_repair_restart_marker', 'select_self_repair_entry_result'),
 ('prepare_self_repair_entry', 'record_self_repair_entry_success'),
 ('select_self_repair_entry_result', 'record_self_repair_entry_success'),
 ('prepare_self_repair_entry', 'record_self_repair_entry_failure'),
 ('select_self_repair_entry_result', 'record_self_repair_entry_failure'),
 ('select_self_repair_entry_result', 'self_repair_entry_terminal'),
 ('record_self_repair_entry_success', 'self_repair_entry_terminal'),
 ('record_self_repair_entry_failure', 'self_repair_entry_terminal')]
_WHEN_BRANCHES = [('record_self_repair_entry_start',
  {'equals': 'run', 'path': 'route', 'upstream': 'classify_self_repair_entry'}),
 ('run_authored_self_repair', {'equals': 'run', 'path': 'route', 'upstream': 'classify_self_repair_entry'}),
 ('write_self_repair_restart_marker',
  {'equals': 'restart', 'path': 'route', 'upstream': 'classify_self_repair_entry_outcome'}),
 ('record_self_repair_entry_success',
  {'equals': 'success', 'path': 'route', 'upstream': 'select_self_repair_entry_result'}),
 ('record_self_repair_entry_failure',
  {'equals': 'failure', 'path': 'route', 'upstream': 'select_self_repair_entry_result'})]
_EFFECTORS = [{'conduction': [], 'id': 'prepare_self_repair_entry', 'when': None},
 {'conduction': ['prepare_self_repair_entry'], 'id': 'classify_self_repair_entry', 'when': None},
 {'conduction': ['prepare_self_repair_entry', 'classify_self_repair_entry'],
  'id': 'record_self_repair_entry_start',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'classify_self_repair_entry'}},
 {'conduction': ['prepare_self_repair_entry', 'classify_self_repair_entry', 'record_self_repair_entry_start'],
  'id': 'run_authored_self_repair',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'classify_self_repair_entry'}},
 {'conduction': ['classify_self_repair_entry', 'run_authored_self_repair'],
  'id': 'record_authored_self_repair',
  'when': None},
 {'conduction': ['record_authored_self_repair'], 'id': 'classify_self_repair_entry_outcome', 'when': None},
 {'conduction': ['prepare_self_repair_entry', 'classify_self_repair_entry_outcome'],
  'id': 'write_self_repair_restart_marker',
  'when': {'equals': 'restart', 'path': 'route', 'upstream': 'classify_self_repair_entry_outcome'}},
 {'conduction': ['prepare_self_repair_entry',
                 'classify_self_repair_entry',
                 'classify_self_repair_entry_outcome',
                 'write_self_repair_restart_marker'],
  'id': 'select_self_repair_entry_result',
  'when': None},
 {'conduction': ['prepare_self_repair_entry', 'select_self_repair_entry_result'],
  'id': 'record_self_repair_entry_success',
  'when': {'equals': 'success', 'path': 'route', 'upstream': 'select_self_repair_entry_result'}},
 {'conduction': ['prepare_self_repair_entry', 'select_self_repair_entry_result'],
  'id': 'record_self_repair_entry_failure',
  'when': {'equals': 'failure', 'path': 'route', 'upstream': 'select_self_repair_entry_result'}},
 {'conduction': ['select_self_repair_entry_result',
                 'record_self_repair_entry_success',
                 'record_self_repair_entry_failure'],
  'id': 'self_repair_entry_terminal',
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

