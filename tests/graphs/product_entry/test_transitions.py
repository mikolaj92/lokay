"""Independent conduction and when metadata for product_entry."""
from __future__ import annotations
import json

_PATH_ID = 'product_entry'
_NODES = {'classify_product_entry_preflight': {'atom': 'classify_product_entry_preflight',
                                      'conduction': [],
                                      'when': None},
 'product_entry_terminal': {'atom': 'product_entry_terminal',
                            'conduction': ['classify_product_entry_preflight', 'run_product_entry_budget'],
                            'when': None},
 'run_product_entry_budget': {'atom': 'run_product_entry_budget',
                              'conduction': ['classify_product_entry_preflight'],
                              'when': {'equals': 'product',
                                       'path': 'route',
                                       'upstream': 'classify_product_entry_preflight'}}}
_COND_EDGES = [('classify_product_entry_preflight', 'run_product_entry_budget'),
 ('classify_product_entry_preflight', 'product_entry_terminal'),
 ('run_product_entry_budget', 'product_entry_terminal')]
_WHEN_BRANCHES = [('run_product_entry_budget',
  {'equals': 'product', 'path': 'route', 'upstream': 'classify_product_entry_preflight'})]
_EFFECTORS = [{'conduction': [], 'id': 'classify_product_entry_preflight', 'when': None},
 {'conduction': ['classify_product_entry_preflight'],
  'id': 'run_product_entry_budget',
  'when': {'equals': 'product', 'path': 'route', 'upstream': 'classify_product_entry_preflight'}},
 {'conduction': ['classify_product_entry_preflight', 'run_product_entry_budget'],
  'id': 'product_entry_terminal',
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

