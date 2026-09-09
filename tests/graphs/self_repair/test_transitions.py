"""Independent conduction and when metadata for self_repair."""
from __future__ import annotations
import json

_PATH_ID = 'self_repair'
_NODES = {'self_repair_activate': {'atom': 'self_repair_activate',
                          'conduction': ['self_repair_push_main'],
                          'when': None},
 'self_repair_close': {'atom': 'self_repair_close', 'conduction': ['self_repair_preflight'], 'when': None},
 'self_repair_commit': {'atom': 'self_repair_commit',
                        'conduction': ['self_repair_prepare', 'self_repair_run_agent'],
                        'when': None},
 'self_repair_preflight': {'atom': 'self_repair_preflight',
                           'conduction': ['self_repair_activate'],
                           'when': None},
 'self_repair_prepare': {'atom': 'self_repair_prepare', 'conduction': [], 'when': None},
 'self_repair_push_main': {'atom': 'self_repair_push_main',
                           'conduction': ['self_repair_prepare',
                                          'self_repair_validate',
                                          'self_repair_commit'],
                           'when': None},
 'self_repair_run_agent': {'atom': 'self_repair_run_agent',
                           'conduction': ['self_repair_prepare'],
                           'when': None},
 'self_repair_validate': {'atom': 'self_repair_validate',
                          'conduction': ['self_repair_prepare', 'self_repair_commit'],
                          'when': None},
 'summarize_self_repair': {'atom': 'summarize_self_repair',
                           'conduction': ['self_repair_preflight',
                                          'self_repair_push_main',
                                          'self_repair_activate',
                                          'self_repair_close'],
                           'when': None}}
_COND_EDGES = [('self_repair_prepare', 'self_repair_run_agent'),
 ('self_repair_prepare', 'self_repair_commit'),
 ('self_repair_run_agent', 'self_repair_commit'),
 ('self_repair_prepare', 'self_repair_validate'),
 ('self_repair_commit', 'self_repair_validate'),
 ('self_repair_prepare', 'self_repair_push_main'),
 ('self_repair_validate', 'self_repair_push_main'),
 ('self_repair_commit', 'self_repair_push_main'),
 ('self_repair_push_main', 'self_repair_activate'),
 ('self_repair_activate', 'self_repair_preflight'),
 ('self_repair_preflight', 'self_repair_close'),
 ('self_repair_preflight', 'summarize_self_repair'),
 ('self_repair_push_main', 'summarize_self_repair'),
 ('self_repair_activate', 'summarize_self_repair'),
 ('self_repair_close', 'summarize_self_repair')]
_WHEN_BRANCHES = []
_EFFECTORS = [{'conduction': [], 'id': 'self_repair_prepare', 'when': None},
 {'conduction': ['self_repair_prepare'], 'id': 'self_repair_run_agent', 'when': None},
 {'conduction': ['self_repair_prepare', 'self_repair_run_agent'], 'id': 'self_repair_commit', 'when': None},
 {'conduction': ['self_repair_prepare', 'self_repair_commit'], 'id': 'self_repair_validate', 'when': None},
 {'conduction': ['self_repair_prepare', 'self_repair_validate', 'self_repair_commit'],
  'id': 'self_repair_push_main',
  'when': None},
 {'conduction': ['self_repair_push_main'], 'id': 'self_repair_activate', 'when': None},
 {'conduction': ['self_repair_activate'], 'id': 'self_repair_preflight', 'when': None},
 {'conduction': ['self_repair_preflight'], 'id': 'self_repair_close', 'when': None},
 {'conduction': ['self_repair_preflight',
                 'self_repair_push_main',
                 'self_repair_activate',
                 'self_repair_close'],
  'id': 'summarize_self_repair',
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

