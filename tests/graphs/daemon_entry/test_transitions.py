"""Independent conduction and when metadata for daemon_entry."""
from __future__ import annotations
import json

_PATH_ID = 'daemon_entry'
_NODES = {'classify_daemon_preflight': {'atom': 'classify_daemon_preflight', 'conduction': [], 'when': None},
 'daemon_entry_terminal': {'atom': 'daemon_entry_terminal',
                           'conduction': ['classify_daemon_preflight',
                                          'run_daemon_product_cycle',
                                          'run_initial_self_repair'],
                           'when': None},
 'run_daemon_product_cycle': {'atom': 'run_daemon_product_cycle',
                              'conduction': ['classify_daemon_preflight'],
                              'when': {'equals': 'product',
                                       'path': 'route',
                                       'upstream': 'classify_daemon_preflight'}},
 'run_initial_self_repair': {'atom': 'run_initial_self_repair',
                             'conduction': ['classify_daemon_preflight'],
                             'when': {'equals': 'repair',
                                      'path': 'route',
                                      'upstream': 'classify_daemon_preflight'}}}
_COND_EDGES = [('classify_daemon_preflight', 'run_daemon_product_cycle'),
 ('classify_daemon_preflight', 'run_initial_self_repair'),
 ('classify_daemon_preflight', 'daemon_entry_terminal'),
 ('run_daemon_product_cycle', 'daemon_entry_terminal'),
 ('run_initial_self_repair', 'daemon_entry_terminal')]
_WHEN_BRANCHES = [('run_daemon_product_cycle',
  {'equals': 'product', 'path': 'route', 'upstream': 'classify_daemon_preflight'}),
 ('run_initial_self_repair', {'equals': 'repair', 'path': 'route', 'upstream': 'classify_daemon_preflight'})]
_EFFECTORS = [{'conduction': [], 'id': 'classify_daemon_preflight', 'when': None},
 {'conduction': ['classify_daemon_preflight'],
  'id': 'run_daemon_product_cycle',
  'when': {'equals': 'product', 'path': 'route', 'upstream': 'classify_daemon_preflight'}},
 {'conduction': ['classify_daemon_preflight'],
  'id': 'run_initial_self_repair',
  'when': {'equals': 'repair', 'path': 'route', 'upstream': 'classify_daemon_preflight'}},
 {'conduction': ['classify_daemon_preflight', 'run_daemon_product_cycle', 'run_initial_self_repair'],
  'id': 'daemon_entry_terminal',
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

