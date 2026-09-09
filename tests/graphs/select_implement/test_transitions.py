"""Independent conduction and when metadata for select_implement."""
from __future__ import annotations
import json

_PATH_ID = 'select_implement'
_NODES = {'implementation_selection_catalog': {'atom': 'implementation_selection_catalog',
                                      'conduction': ['prepare_implementation_selection'],
                                      'when': None},
 'persist_implementation_selection': {'atom': 'persist_implementation_selection',
                                      'conduction': ['implementation_selection_catalog'],
                                      'when': None},
 'prepare_implementation_selection': {'atom': 'prepare_implementation_selection',
                                      'conduction': [],
                                      'when': None},
 'summarize_implementation_selection': {'atom': 'summarize_implementation_selection',
                                        'conduction': ['persist_implementation_selection'],
                                        'when': None}}
_COND_EDGES = [('prepare_implementation_selection', 'implementation_selection_catalog'),
 ('implementation_selection_catalog', 'persist_implementation_selection'),
 ('persist_implementation_selection', 'summarize_implementation_selection')]
_WHEN_BRANCHES = []
_EFFECTORS = [{'conduction': [], 'id': 'prepare_implementation_selection', 'when': None},
 {'conduction': ['prepare_implementation_selection'], 'id': 'implementation_selection_catalog', 'when': None},
 {'conduction': ['implementation_selection_catalog'], 'id': 'persist_implementation_selection', 'when': None},
 {'conduction': ['persist_implementation_selection'],
  'id': 'summarize_implementation_selection',
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

