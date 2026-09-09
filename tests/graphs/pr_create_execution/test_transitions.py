"""Independent conduction and when metadata for pr_create_execution."""
from __future__ import annotations
import json

_PATH_ID = 'pr_create_execution'
_NODES = {'classify_pr_create_issue': {'atom': 'classify_pr_create_issue',
                              'conduction': ['record_existing_delivery_pr', 'read_pr_create_issue'],
                              'when': None},
 'create_pull_request_effect': {'atom': 'create_pull_request_effect',
                                'conduction': ['prepare_pr_create_request', 'classify_pr_create_issue'],
                                'when': {'equals': 'create',
                                         'path': 'route',
                                         'upstream': 'classify_pr_create_issue'}},
 'find_existing_delivery_pr': {'atom': 'find_existing_delivery_pr',
                               'conduction': ['prepare_pr_create_request'],
                               'when': None},
 'pr_create_terminal': {'atom': 'pr_create_terminal',
                        'conduction': ['prepare_pr_create_request',
                                       'record_existing_delivery_pr',
                                       'read_pr_create_issue',
                                       'classify_pr_create_issue',
                                       'create_pull_request_effect'],
                        'when': None},
 'prepare_pr_create_request': {'atom': 'prepare_pr_create_request', 'conduction': [], 'when': None},
 'read_pr_create_issue': {'atom': 'read_pr_create_issue',
                          'conduction': ['prepare_pr_create_request', 'record_existing_delivery_pr'],
                          'when': {'equals': 'none',
                                   'path': 'route',
                                   'upstream': 'record_existing_delivery_pr'}},
 'record_existing_delivery_pr': {'atom': 'record_existing_delivery_pr',
                                 'conduction': ['find_existing_delivery_pr'],
                                 'when': None}}
_COND_EDGES = [('prepare_pr_create_request', 'find_existing_delivery_pr'),
 ('find_existing_delivery_pr', 'record_existing_delivery_pr'),
 ('prepare_pr_create_request', 'read_pr_create_issue'),
 ('record_existing_delivery_pr', 'read_pr_create_issue'),
 ('record_existing_delivery_pr', 'classify_pr_create_issue'),
 ('read_pr_create_issue', 'classify_pr_create_issue'),
 ('prepare_pr_create_request', 'create_pull_request_effect'),
 ('classify_pr_create_issue', 'create_pull_request_effect'),
 ('prepare_pr_create_request', 'pr_create_terminal'),
 ('record_existing_delivery_pr', 'pr_create_terminal'),
 ('read_pr_create_issue', 'pr_create_terminal'),
 ('classify_pr_create_issue', 'pr_create_terminal'),
 ('create_pull_request_effect', 'pr_create_terminal')]
_WHEN_BRANCHES = [('read_pr_create_issue', {'equals': 'none', 'path': 'route', 'upstream': 'record_existing_delivery_pr'}),
 ('create_pull_request_effect',
  {'equals': 'create', 'path': 'route', 'upstream': 'classify_pr_create_issue'})]
_EFFECTORS = [{'conduction': [], 'id': 'prepare_pr_create_request', 'when': None},
 {'conduction': ['prepare_pr_create_request'], 'id': 'find_existing_delivery_pr', 'when': None},
 {'conduction': ['find_existing_delivery_pr'], 'id': 'record_existing_delivery_pr', 'when': None},
 {'conduction': ['prepare_pr_create_request', 'record_existing_delivery_pr'],
  'id': 'read_pr_create_issue',
  'when': {'equals': 'none', 'path': 'route', 'upstream': 'record_existing_delivery_pr'}},
 {'conduction': ['record_existing_delivery_pr', 'read_pr_create_issue'],
  'id': 'classify_pr_create_issue',
  'when': None},
 {'conduction': ['prepare_pr_create_request', 'classify_pr_create_issue'],
  'id': 'create_pull_request_effect',
  'when': {'equals': 'create', 'path': 'route', 'upstream': 'classify_pr_create_issue'}},
 {'conduction': ['prepare_pr_create_request',
                 'record_existing_delivery_pr',
                 'read_pr_create_issue',
                 'classify_pr_create_issue',
                 'create_pull_request_effect'],
  'id': 'pr_create_terminal',
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

