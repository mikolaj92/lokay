"""Independent conduction and when metadata for pr_triage_department."""
from __future__ import annotations
import json

_PATH_ID = 'pr_triage_department'
_NODES = {'list_pr_sieve': {'atom': 'list_pr_sieve', 'conduction': [], 'when': None},
 'run_pr_sieve': {'atom': 'run_pr_sieve',
                  'conduction': ['select_pr_sieve'],
                  'when': {'equals': 'pr', 'path': 'route', 'upstream': 'select_pr_sieve'}},
 'select_pr_sieve': {'atom': 'select_pr_sieve', 'conduction': ['list_pr_sieve'], 'when': None},
 'select_pr_triage_verdict': {'atom': 'select_pr_triage_verdict',
                              'conduction': ['select_pr_sieve', 'run_pr_sieve'],
                              'when': None},
 'summarize_pr_triage_department': {'atom': 'summarize_pr_triage_department',
                                    'conduction': ['select_pr_sieve',
                                                   'run_pr_sieve',
                                                   'select_pr_triage_verdict'],
                                    'when': None}}
_COND_EDGES = [('list_pr_sieve', 'select_pr_sieve'),
 ('select_pr_sieve', 'run_pr_sieve'),
 ('select_pr_sieve', 'select_pr_triage_verdict'),
 ('run_pr_sieve', 'select_pr_triage_verdict'),
 ('select_pr_sieve', 'summarize_pr_triage_department'),
 ('run_pr_sieve', 'summarize_pr_triage_department'),
 ('select_pr_triage_verdict', 'summarize_pr_triage_department')]
_WHEN_BRANCHES = [('run_pr_sieve', {'equals': 'pr', 'path': 'route', 'upstream': 'select_pr_sieve'})]
_EFFECTORS = [{'conduction': [], 'id': 'list_pr_sieve', 'when': None},
 {'conduction': ['list_pr_sieve'], 'id': 'select_pr_sieve', 'when': None},
 {'conduction': ['select_pr_sieve'],
  'id': 'run_pr_sieve',
  'when': {'equals': 'pr', 'path': 'route', 'upstream': 'select_pr_sieve'}},
 {'conduction': ['select_pr_sieve', 'run_pr_sieve'], 'id': 'select_pr_triage_verdict', 'when': None},
 {'conduction': ['select_pr_sieve', 'run_pr_sieve', 'select_pr_triage_verdict'],
  'id': 'summarize_pr_triage_department',
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

