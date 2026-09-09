"""Independent conduction and when metadata for daemon_cycle."""
from __future__ import annotations
import json

_PATH_ID = 'daemon_cycle'
_NODES = {'last_pass_moving': {'atom': 'last_pass_moving', 'conduction': [], 'when': None},
 'recovery_factory': {'atom': 'recovery_factory',
                      'conduction': ['select_repair_route', 'recovery_run_self_repair'],
                      'when': {'equals': 'factory', 'path': 'route', 'upstream': 'select_repair_route'}},
 'recovery_incident': {'atom': 'recovery_incident',
                       'conduction': ['select_repair_route'],
                       'when': {'equals': 'repair', 'path': 'route', 'upstream': 'select_repair_route'}},
 'recovery_run_self_repair': {'atom': 'recovery_run_self_repair',
                              'conduction': ['select_repair_route', 'recovery_incident'],
                              'when': {'equals': 'repair',
                                       'path': 'route',
                                       'upstream': 'select_repair_route'}},
 'select_repair_route': {'atom': 'select_repair_route', 'conduction': ['last_pass_moving'], 'when': None},
 'summarize_daemon_cycle': {'atom': 'summarize_daemon_cycle',
                            'conduction': ['select_repair_route',
                                           'recovery_factory',
                                           'recovery_run_self_repair'],
                            'when': None}}
_COND_EDGES = [('last_pass_moving', 'select_repair_route'),
 ('select_repair_route', 'recovery_incident'),
 ('select_repair_route', 'recovery_run_self_repair'),
 ('recovery_incident', 'recovery_run_self_repair'),
 ('select_repair_route', 'recovery_factory'),
 ('recovery_run_self_repair', 'recovery_factory'),
 ('select_repair_route', 'summarize_daemon_cycle'),
 ('recovery_factory', 'summarize_daemon_cycle'),
 ('recovery_run_self_repair', 'summarize_daemon_cycle')]
_WHEN_BRANCHES = [('recovery_incident', {'equals': 'repair', 'path': 'route', 'upstream': 'select_repair_route'}),
 ('recovery_run_self_repair', {'equals': 'repair', 'path': 'route', 'upstream': 'select_repair_route'}),
 ('recovery_factory', {'equals': 'factory', 'path': 'route', 'upstream': 'select_repair_route'})]
_EFFECTORS = [{'conduction': [], 'id': 'last_pass_moving', 'when': None},
 {'conduction': ['last_pass_moving'], 'id': 'select_repair_route', 'when': None},
 {'conduction': ['select_repair_route'],
  'id': 'recovery_incident',
  'when': {'equals': 'repair', 'path': 'route', 'upstream': 'select_repair_route'}},
 {'conduction': ['select_repair_route', 'recovery_incident'],
  'id': 'recovery_run_self_repair',
  'when': {'equals': 'repair', 'path': 'route', 'upstream': 'select_repair_route'}},
 {'conduction': ['select_repair_route', 'recovery_run_self_repair'],
  'id': 'recovery_factory',
  'when': {'equals': 'factory', 'path': 'route', 'upstream': 'select_repair_route'}},
 {'conduction': ['select_repair_route', 'recovery_factory', 'recovery_run_self_repair'],
  'id': 'summarize_daemon_cycle',
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

