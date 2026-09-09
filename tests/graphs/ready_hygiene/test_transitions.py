"""Independent conduction and when metadata for ready_hygiene."""
from __future__ import annotations
import json

_PATH_ID = 'ready_hygiene'
_NODES = {'prepare_ready_hygiene': {'atom': 'prepare_ready_hygiene', 'conduction': [], 'when': None},
 'ready_hygiene_catalog': {'atom': 'ready_hygiene_catalog',
                           'conduction': ['prepare_ready_hygiene'],
                           'when': None},
 'update_ready_hygiene_stamp': {'atom': 'update_ready_hygiene_stamp',
                                'conduction': ['ready_hygiene_catalog'],
                                'when': None}}
_COND_EDGES = [('prepare_ready_hygiene', 'ready_hygiene_catalog'), ('ready_hygiene_catalog', 'update_ready_hygiene_stamp')]
_WHEN_BRANCHES = []
_EFFECTORS = [{'conduction': [], 'id': 'prepare_ready_hygiene', 'when': None},
 {'conduction': ['prepare_ready_hygiene'], 'id': 'ready_hygiene_catalog', 'when': None},
 {'conduction': ['ready_hygiene_catalog'], 'id': 'update_ready_hygiene_stamp', 'when': None}]

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

