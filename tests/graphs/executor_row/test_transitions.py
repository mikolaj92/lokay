"""Independent conduction and when metadata for executor_row."""
from __future__ import annotations
import json

_PATH_ID = 'executor_row'
_NODES = {'issues_launch_pr': {'atom': 'issues_launch_pr',
                      'conduction': ['select_issue_executor'],
                      'when': {'equals': 'do', 'path': 'route', 'upstream': 'select_issue_executor'}},
 'select_issue_do_row': {'atom': 'select_issue_do_row', 'conduction': ['select_next_issue'], 'when': None},
 'select_issue_executor': {'atom': 'select_issue_executor',
                           'conduction': ['select_issue_do_row'],
                           'when': None},
 'select_next_issue': {'atom': 'select_next_issue', 'conduction': [], 'when': None},
 'summarize_executor_row': {'atom': 'summarize_executor_row',
                            'conduction': ['select_next_issue',
                                           'select_issue_do_row',
                                           'select_issue_executor',
                                           'issues_launch_pr'],
                            'when': None}}
_COND_EDGES = [('select_next_issue', 'select_issue_do_row'),
 ('select_issue_do_row', 'select_issue_executor'),
 ('select_issue_executor', 'issues_launch_pr'),
 ('select_next_issue', 'summarize_executor_row'),
 ('select_issue_do_row', 'summarize_executor_row'),
 ('select_issue_executor', 'summarize_executor_row'),
 ('issues_launch_pr', 'summarize_executor_row')]
_WHEN_BRANCHES = [('issues_launch_pr', {'equals': 'do', 'path': 'route', 'upstream': 'select_issue_executor'})]
_EFFECTORS = [{'conduction': [], 'id': 'select_next_issue', 'when': None},
 {'conduction': ['select_next_issue'], 'id': 'select_issue_do_row', 'when': None},
 {'conduction': ['select_issue_do_row'], 'id': 'select_issue_executor', 'when': None},
 {'conduction': ['select_issue_executor'],
  'id': 'issues_launch_pr',
  'when': {'equals': 'do', 'path': 'route', 'upstream': 'select_issue_executor'}},
 {'conduction': ['select_next_issue', 'select_issue_do_row', 'select_issue_executor', 'issues_launch_pr'],
  'id': 'summarize_executor_row',
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

