"""Independent conduction and when metadata for status_snapshot."""
from __future__ import annotations
import json

_PATH_ID = 'status_snapshot'
_NODES = {'classify_status_readiness': {'atom': 'classify_status_readiness',
                               'conduction': ['read_status_config'],
                               'when': None},
 'describe_status_graphs': {'atom': 'describe_status_graphs',
                            'conduction': ['read_status_config'],
                            'when': None},
 'read_status_clone_facts': {'atom': 'read_status_clone_facts',
                             'conduction': ['read_status_config'],
                             'when': None},
 'read_status_config': {'atom': 'read_status_config', 'conduction': [], 'when': None},
 'read_status_lease': {'atom': 'read_status_lease', 'conduction': ['read_status_config'], 'when': None},
 'read_status_pass_receipt': {'atom': 'read_status_pass_receipt',
                              'conduction': ['read_status_config'],
                              'when': None},
 'read_status_repo_locks': {'atom': 'read_status_repo_locks',
                            'conduction': ['read_status_config'],
                            'when': None},
 'read_status_work_units': {'atom': 'read_status_work_units',
                            'conduction': ['read_status_config'],
                            'when': None},
 'record_status_preflight': {'atom': 'record_status_preflight',
                             'conduction': ['read_status_config', 'run_status_preflight'],
                             'when': None},
 'reduce_status_snapshot': {'atom': 'reduce_status_snapshot',
                            'conduction': ['read_status_config',
                                           'classify_status_readiness',
                                           'read_status_clone_facts',
                                           'read_status_lease',
                                           'read_status_pass_receipt',
                                           'read_status_work_units',
                                           'read_status_repo_locks',
                                           'describe_status_graphs',
                                           'record_status_preflight'],
                            'when': None},
 'run_status_preflight': {'atom': 'run_status_preflight',
                          'conduction': ['read_status_config'],
                          'when': {'equals': True,
                                   'path': 'preflight_requested',
                                   'upstream': 'read_status_config'}},
 'status_snapshot_terminal': {'atom': 'status_snapshot_terminal',
                              'conduction': ['reduce_status_snapshot'],
                              'when': None}}
_COND_EDGES = [('read_status_config', 'classify_status_readiness'),
 ('read_status_config', 'read_status_clone_facts'),
 ('read_status_config', 'read_status_lease'),
 ('read_status_config', 'read_status_pass_receipt'),
 ('read_status_config', 'read_status_work_units'),
 ('read_status_config', 'read_status_repo_locks'),
 ('read_status_config', 'describe_status_graphs'),
 ('read_status_config', 'run_status_preflight'),
 ('read_status_config', 'record_status_preflight'),
 ('run_status_preflight', 'record_status_preflight'),
 ('read_status_config', 'reduce_status_snapshot'),
 ('classify_status_readiness', 'reduce_status_snapshot'),
 ('read_status_clone_facts', 'reduce_status_snapshot'),
 ('read_status_lease', 'reduce_status_snapshot'),
 ('read_status_pass_receipt', 'reduce_status_snapshot'),
 ('read_status_work_units', 'reduce_status_snapshot'),
 ('read_status_repo_locks', 'reduce_status_snapshot'),
 ('describe_status_graphs', 'reduce_status_snapshot'),
 ('record_status_preflight', 'reduce_status_snapshot'),
 ('reduce_status_snapshot', 'status_snapshot_terminal')]
_WHEN_BRANCHES = [('run_status_preflight', {'equals': True, 'path': 'preflight_requested', 'upstream': 'read_status_config'})]
_EFFECTORS = [{'conduction': [], 'id': 'read_status_config', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'classify_status_readiness', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'read_status_clone_facts', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'read_status_lease', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'read_status_pass_receipt', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'read_status_work_units', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'read_status_repo_locks', 'when': None},
 {'conduction': ['read_status_config'], 'id': 'describe_status_graphs', 'when': None},
 {'conduction': ['read_status_config'],
  'id': 'run_status_preflight',
  'when': {'equals': True, 'path': 'preflight_requested', 'upstream': 'read_status_config'}},
 {'conduction': ['read_status_config', 'run_status_preflight'],
  'id': 'record_status_preflight',
  'when': None},
 {'conduction': ['read_status_config',
                 'classify_status_readiness',
                 'read_status_clone_facts',
                 'read_status_lease',
                 'read_status_pass_receipt',
                 'read_status_work_units',
                 'read_status_repo_locks',
                 'describe_status_graphs',
                 'record_status_preflight'],
  'id': 'reduce_status_snapshot',
  'when': None},
 {'conduction': ['reduce_status_snapshot'], 'id': 'status_snapshot_terminal', 'when': None}]

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

