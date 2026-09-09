"""Independent conduction and when metadata for self_repair_department."""
from __future__ import annotations
import json

_PATH_ID = 'self_repair_department'
_NODES = {'invoke_self_repair': {'atom': 'invoke_self_repair',
                        'conduction': ['open_self_repair_incident'],
                        'when': {'equals': 'run', 'path': 'route', 'upstream': 'open_self_repair_incident'}},
 'open_self_repair_incident': {'atom': 'open_self_repair_incident', 'conduction': [], 'when': None}}
_COND_EDGES = [('open_self_repair_incident', 'invoke_self_repair')]
_WHEN_BRANCHES = [('invoke_self_repair', {'equals': 'run', 'path': 'route', 'upstream': 'open_self_repair_incident'})]
_EFFECTORS = [{'conduction': [], 'id': 'open_self_repair_incident', 'when': None},
 {'conduction': ['open_self_repair_incident'],
  'id': 'invoke_self_repair',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'open_self_repair_incident'}}]

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

