"""Independent conduction and when metadata for triage_dispatch."""
from __future__ import annotations
import json

_PATH_ID = 'triage_dispatch'
_NODES = {'check_triage_stuck': {'atom': 'check_triage_stuck',
                        'conduction': ['select_triage_target'],
                        'when': {'equals': 'target', 'path': 'route', 'upstream': 'select_triage_target'}},
 'record_triage_dispatch': {'atom': 'record_triage_dispatch',
                            'conduction': ['select_triage_run'],
                            'when': None},
 'run_issue_triage_subflow': {'atom': 'run_issue_triage_subflow',
                              'conduction': ['select_triage_gate'],
                              'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_triage_gate'}},
 'select_triage_gate': {'atom': 'select_triage_gate',
                        'conduction': ['select_triage_target', 'check_triage_stuck'],
                        'when': None},
 'select_triage_run': {'atom': 'select_triage_run',
                       'conduction': ['select_triage_gate', 'run_issue_triage_subflow'],
                       'when': None},
 'select_triage_target': {'atom': 'select_triage_target', 'conduction': [], 'when': None},
 'summarize_triage_dispatch': {'atom': 'summarize_triage_dispatch',
                               'conduction': ['record_triage_dispatch'],
                               'when': None}}
_COND_EDGES = [('select_triage_target', 'check_triage_stuck'),
 ('select_triage_target', 'select_triage_gate'),
 ('check_triage_stuck', 'select_triage_gate'),
 ('select_triage_gate', 'run_issue_triage_subflow'),
 ('select_triage_gate', 'select_triage_run'),
 ('run_issue_triage_subflow', 'select_triage_run'),
 ('select_triage_run', 'record_triage_dispatch'),
 ('record_triage_dispatch', 'summarize_triage_dispatch')]
_WHEN_BRANCHES = [('check_triage_stuck', {'equals': 'target', 'path': 'route', 'upstream': 'select_triage_target'}),
 ('run_issue_triage_subflow', {'equals': 'run', 'path': 'route', 'upstream': 'select_triage_gate'})]
_EFFECTORS = [{'conduction': [], 'id': 'select_triage_target', 'when': None},
 {'conduction': ['select_triage_target'],
  'id': 'check_triage_stuck',
  'when': {'equals': 'target', 'path': 'route', 'upstream': 'select_triage_target'}},
 {'conduction': ['select_triage_target', 'check_triage_stuck'], 'id': 'select_triage_gate', 'when': None},
 {'conduction': ['select_triage_gate'],
  'id': 'run_issue_triage_subflow',
  'when': {'equals': 'run', 'path': 'route', 'upstream': 'select_triage_gate'}},
 {'conduction': ['select_triage_gate', 'run_issue_triage_subflow'], 'id': 'select_triage_run', 'when': None},
 {'conduction': ['select_triage_run'], 'id': 'record_triage_dispatch', 'when': None},
 {'conduction': ['record_triage_dispatch'], 'id': 'summarize_triage_dispatch', 'when': None}]

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

