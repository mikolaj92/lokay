"""Independent conduction and when metadata for leftover_closeout."""
from __future__ import annotations
import json

_PATH_ID = 'leftover_closeout'
_NODES = {'leftover_catalog': {'atom': 'leftover_catalog', 'conduction': ['prepare_leftover_closeout'], 'when': None},
 'prepare_leftover_closeout': {'atom': 'prepare_leftover_closeout', 'conduction': [], 'when': None},
 'update_leftover_stamp': {'atom': 'update_leftover_stamp', 'conduction': ['leftover_catalog'], 'when': None}}
_COND_EDGES = [('prepare_leftover_closeout', 'leftover_catalog'), ('leftover_catalog', 'update_leftover_stamp')]
_WHEN_BRANCHES = []
_EFFECTORS = [{'conduction': [], 'id': 'prepare_leftover_closeout', 'when': None},
 {'conduction': ['prepare_leftover_closeout'], 'id': 'leftover_catalog', 'when': None},
 {'conduction': ['leftover_catalog'], 'id': 'update_leftover_stamp', 'when': None}]

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

