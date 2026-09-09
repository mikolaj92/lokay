"""Independent conduction and when metadata for executor_department."""
from __future__ import annotations
import json

_PATH_ID = 'executor_department'
_NODES = {'list_open_issues': {'atom': 'list_open_issues', 'conduction': [], 'when': None},
 'run_executor_rows': {'atom': 'run_executor_rows', 'conduction': ['list_open_issues'], 'when': None},
 'summarize_executor_department': {'atom': 'summarize_executor_department',
                                   'conduction': ['list_open_issues', 'run_executor_rows'],
                                   'when': None}}
_COND_EDGES = [('list_open_issues', 'run_executor_rows'),
 ('list_open_issues', 'summarize_executor_department'),
 ('run_executor_rows', 'summarize_executor_department')]
_WHEN_BRANCHES = []
_EFFECTORS = [{'conduction': [], 'id': 'list_open_issues', 'when': None},
 {'conduction': ['list_open_issues'], 'id': 'run_executor_rows', 'when': None},
 {'conduction': ['list_open_issues', 'run_executor_rows'],
  'id': 'summarize_executor_department',
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

