"""Independent conduction and when metadata for queue_conflict."""
from __future__ import annotations
import json

_PATH_ID = 'queue_conflict'
_NODES = {'add_queue_tracker_label': {'atom': 'add_queue_tracker_label',
                             'conduction': ['select_queue_tracker'],
                             'when': {'equals': 'tracker',
                                      'path': 'route',
                                      'upstream': 'select_queue_tracker'}},
 'advance_implementation_selection': {'atom': 'advance_implementation_selection',
                                      'conduction': ['record_queue_conflict'],
                                      'when': None},
 'check_queue_covering_pr': {'atom': 'check_queue_covering_pr',
                             'conduction': ['select_queue_conflict_candidate'],
                             'when': {'equals': 'candidate',
                                      'path': 'route',
                                      'upstream': 'select_queue_conflict_candidate'}},
 'queue_conflict_agent': {'atom': 'queue_conflict_agent',
                          'conduction': ['select_queue_conflict_gate'],
                          'when': {'equals': 'agent',
                                   'path': 'route',
                                   'upstream': 'select_queue_conflict_gate'}},
 'queue_conflict_retry_agent': {'atom': 'queue_conflict_retry_agent',
                                'conduction': ['validate_queue_conflict', 'select_queue_conflict_gate'],
                                'when': {'equals': 'retry',
                                         'path': 'route',
                                         'upstream': 'validate_queue_conflict'}},
 'record_queue_conflict': {'atom': 'record_queue_conflict',
                           'conduction': ['select_queue_conflict_outcome',
                                          'remove_queue_ready_label',
                                          'add_queue_tracker_label'],
                           'when': None},
 'remove_queue_ready_label': {'atom': 'remove_queue_ready_label',
                              'conduction': ['select_queue_conflict_outcome'],
                              'when': {'equals': 'close',
                                       'path': 'route',
                                       'upstream': 'select_queue_conflict_outcome'}},
 'select_queue_conflict_candidate': {'atom': 'select_queue_conflict_candidate',
                                     'conduction': [],
                                     'when': None},
 'select_queue_conflict_gate': {'atom': 'select_queue_conflict_gate',
                                'conduction': ['select_queue_conflict_candidate', 'check_queue_covering_pr'],
                                'when': None},
 'select_queue_conflict_outcome': {'atom': 'select_queue_conflict_outcome',
                                   'conduction': ['select_queue_conflict_candidate',
                                                  'select_queue_conflict_gate',
                                                  'validate_queue_conflict',
                                                  'validate_queue_conflict_retry'],
                                   'when': None},
 'select_queue_tracker': {'atom': 'select_queue_tracker',
                          'conduction': ['select_queue_conflict_outcome', 'remove_queue_ready_label'],
                          'when': None},
 'summarize_queue_conflict': {'atom': 'summarize_queue_conflict',
                              'conduction': ['select_queue_conflict_candidate',
                                             'record_queue_conflict',
                                             'advance_implementation_selection'],
                              'when': None},
 'validate_queue_conflict': {'atom': 'validate_queue_conflict',
                             'conduction': ['queue_conflict_agent'],
                             'when': None},
 'validate_queue_conflict_retry': {'atom': 'validate_queue_conflict_retry',
                                   'conduction': ['queue_conflict_retry_agent'],
                                   'when': None}}
_COND_EDGES = [('select_queue_conflict_candidate', 'check_queue_covering_pr'),
 ('select_queue_conflict_candidate', 'select_queue_conflict_gate'),
 ('check_queue_covering_pr', 'select_queue_conflict_gate'),
 ('select_queue_conflict_gate', 'queue_conflict_agent'),
 ('queue_conflict_agent', 'validate_queue_conflict'),
 ('validate_queue_conflict', 'queue_conflict_retry_agent'),
 ('select_queue_conflict_gate', 'queue_conflict_retry_agent'),
 ('queue_conflict_retry_agent', 'validate_queue_conflict_retry'),
 ('select_queue_conflict_candidate', 'select_queue_conflict_outcome'),
 ('select_queue_conflict_gate', 'select_queue_conflict_outcome'),
 ('validate_queue_conflict', 'select_queue_conflict_outcome'),
 ('validate_queue_conflict_retry', 'select_queue_conflict_outcome'),
 ('select_queue_conflict_outcome', 'remove_queue_ready_label'),
 ('select_queue_conflict_outcome', 'select_queue_tracker'),
 ('remove_queue_ready_label', 'select_queue_tracker'),
 ('select_queue_tracker', 'add_queue_tracker_label'),
 ('select_queue_conflict_outcome', 'record_queue_conflict'),
 ('remove_queue_ready_label', 'record_queue_conflict'),
 ('add_queue_tracker_label', 'record_queue_conflict'),
 ('record_queue_conflict', 'advance_implementation_selection'),
 ('select_queue_conflict_candidate', 'summarize_queue_conflict'),
 ('record_queue_conflict', 'summarize_queue_conflict'),
 ('advance_implementation_selection', 'summarize_queue_conflict')]
_WHEN_BRANCHES = [('check_queue_covering_pr',
  {'equals': 'candidate', 'path': 'route', 'upstream': 'select_queue_conflict_candidate'}),
 ('queue_conflict_agent', {'equals': 'agent', 'path': 'route', 'upstream': 'select_queue_conflict_gate'}),
 ('queue_conflict_retry_agent', {'equals': 'retry', 'path': 'route', 'upstream': 'validate_queue_conflict'}),
 ('remove_queue_ready_label',
  {'equals': 'close', 'path': 'route', 'upstream': 'select_queue_conflict_outcome'}),
 ('add_queue_tracker_label', {'equals': 'tracker', 'path': 'route', 'upstream': 'select_queue_tracker'})]
_EFFECTORS = [{'conduction': [], 'id': 'select_queue_conflict_candidate', 'when': None},
 {'conduction': ['select_queue_conflict_candidate'],
  'id': 'check_queue_covering_pr',
  'when': {'equals': 'candidate', 'path': 'route', 'upstream': 'select_queue_conflict_candidate'}},
 {'conduction': ['select_queue_conflict_candidate', 'check_queue_covering_pr'],
  'id': 'select_queue_conflict_gate',
  'when': None},
 {'conduction': ['select_queue_conflict_gate'],
  'id': 'queue_conflict_agent',
  'when': {'equals': 'agent', 'path': 'route', 'upstream': 'select_queue_conflict_gate'}},
 {'conduction': ['queue_conflict_agent'], 'id': 'validate_queue_conflict', 'when': None},
 {'conduction': ['validate_queue_conflict', 'select_queue_conflict_gate'],
  'id': 'queue_conflict_retry_agent',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_queue_conflict'}},
 {'conduction': ['queue_conflict_retry_agent'], 'id': 'validate_queue_conflict_retry', 'when': None},
 {'conduction': ['select_queue_conflict_candidate',
                 'select_queue_conflict_gate',
                 'validate_queue_conflict',
                 'validate_queue_conflict_retry'],
  'id': 'select_queue_conflict_outcome',
  'when': None},
 {'conduction': ['select_queue_conflict_outcome'],
  'id': 'remove_queue_ready_label',
  'when': {'equals': 'close', 'path': 'route', 'upstream': 'select_queue_conflict_outcome'}},
 {'conduction': ['select_queue_conflict_outcome', 'remove_queue_ready_label'],
  'id': 'select_queue_tracker',
  'when': None},
 {'conduction': ['select_queue_tracker'],
  'id': 'add_queue_tracker_label',
  'when': {'equals': 'tracker', 'path': 'route', 'upstream': 'select_queue_tracker'}},
 {'conduction': ['select_queue_conflict_outcome', 'remove_queue_ready_label', 'add_queue_tracker_label'],
  'id': 'record_queue_conflict',
  'when': None},
 {'conduction': ['record_queue_conflict'], 'id': 'advance_implementation_selection', 'when': None},
 {'conduction': ['select_queue_conflict_candidate',
                 'record_queue_conflict',
                 'advance_implementation_selection'],
  'id': 'summarize_queue_conflict',
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

