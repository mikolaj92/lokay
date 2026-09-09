"""Independent conduction and when metadata for issue_sieve_row."""
from __future__ import annotations
import json

_PATH_ID = 'issue_sieve_row'
_NODES = {'issues_run_triage': {'atom': 'issues_run_triage',
                       'conduction': ['select_next_issue'],
                       'when': {'equals': 'issue', 'path': 'route', 'upstream': 'select_next_issue'}},
 'run_issue_sieve_split': {'atom': 'run_issue_sieve_split',
                           'conduction': ['select_issue_sieve'],
                           'when': {'equals': 'split', 'path': 'route', 'upstream': 'select_issue_sieve'}},
 'select_issue_sieve': {'atom': 'select_issue_sieve',
                        'conduction': ['select_next_issue', 'issues_run_triage'],
                        'when': None},
 'select_next_issue': {'atom': 'select_next_issue', 'conduction': [], 'when': None},
 'summarize_issue_sieve_row': {'atom': 'summarize_issue_sieve_row',
                               'conduction': ['select_next_issue',
                                              'issues_run_triage',
                                              'select_issue_sieve',
                                              'run_issue_sieve_split'],
                               'when': None}}
_COND_EDGES = [('select_next_issue', 'issues_run_triage'),
 ('select_next_issue', 'select_issue_sieve'),
 ('issues_run_triage', 'select_issue_sieve'),
 ('select_issue_sieve', 'run_issue_sieve_split'),
 ('select_next_issue', 'summarize_issue_sieve_row'),
 ('issues_run_triage', 'summarize_issue_sieve_row'),
 ('select_issue_sieve', 'summarize_issue_sieve_row'),
 ('run_issue_sieve_split', 'summarize_issue_sieve_row')]
_WHEN_BRANCHES = [('issues_run_triage', {'equals': 'issue', 'path': 'route', 'upstream': 'select_next_issue'}),
 ('run_issue_sieve_split', {'equals': 'split', 'path': 'route', 'upstream': 'select_issue_sieve'})]
_EFFECTORS = [{'conduction': [], 'id': 'select_next_issue', 'when': None},
 {'conduction': ['select_next_issue'],
  'id': 'issues_run_triage',
  'when': {'equals': 'issue', 'path': 'route', 'upstream': 'select_next_issue'}},
 {'conduction': ['select_next_issue', 'issues_run_triage'], 'id': 'select_issue_sieve', 'when': None},
 {'conduction': ['select_issue_sieve'],
  'id': 'run_issue_sieve_split',
  'when': {'equals': 'split', 'path': 'route', 'upstream': 'select_issue_sieve'}},
 {'conduction': ['select_next_issue', 'issues_run_triage', 'select_issue_sieve', 'run_issue_sieve_split'],
  'id': 'summarize_issue_sieve_row',
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

