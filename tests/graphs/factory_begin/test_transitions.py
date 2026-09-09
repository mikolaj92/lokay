"""Independent conduction and when metadata for factory_begin."""
from __future__ import annotations
import json

_PATH_ID = 'factory_begin'
_NODES = {'attach_factory_stuck': {'atom': 'attach_factory_stuck',
                          'conduction': ['build_factory_begin_state',
                                         'seed_factory_occupancy',
                                         'read_factory_stuck'],
                          'when': None},
 'build_factory_begin_state': {'atom': 'build_factory_begin_state',
                               'conduction': ['load_factory_config',
                                              'select_factory_scope',
                                              'read_factory_stuck',
                                              'create_factory_pass_dir'],
                               'when': None},
 'build_factory_working_state': {'atom': 'build_factory_working_state',
                                 'conduction': ['read_factory_stuck'],
                                 'when': None},
 'classify_leftover_remaining': {'atom': 'classify_leftover_remaining',
                                 'conduction': ['persist_factory_tick'],
                                 'when': None},
 'create_factory_pass_dir': {'atom': 'create_factory_pass_dir',
                             'conduction': ['load_factory_config', 'select_factory_scope'],
                             'when': None},
 'load_factory_config': {'atom': 'load_factory_config', 'conduction': ['probe_factory_host'], 'when': None},
 'merge_leftover_remaining': {'atom': 'merge_leftover_remaining',
                              'conduction': ['persist_factory_tick', 'classify_leftover_remaining'],
                              'when': None},
 'persist_factory_begin_state': {'atom': 'persist_factory_begin_state',
                                 'conduction': ['create_factory_pass_dir', 'attach_factory_stuck'],
                                 'when': None},
 'persist_factory_tick': {'atom': 'persist_factory_tick',
                          'conduction': ['probe_factory_host',
                                         'read_factory_stuck',
                                         'create_factory_pass_dir',
                                         'attach_factory_stuck',
                                         'persist_factory_working_state'],
                          'when': None},
 'persist_factory_working_state': {'atom': 'persist_factory_working_state',
                                   'conduction': ['create_factory_pass_dir',
                                                  'attach_factory_stuck',
                                                  'persist_factory_begin_state'],
                                   'when': None},
 'probe_factory_host': {'atom': 'probe_factory_host', 'conduction': [], 'when': None},
 'read_factory_stuck': {'atom': 'read_factory_stuck', 'conduction': ['load_factory_config'], 'when': None},
 'seed_factory_occupancy': {'atom': 'seed_factory_occupancy',
                            'conduction': ['build_factory_working_state'],
                            'when': None},
 'select_factory_scope': {'atom': 'select_factory_scope',
                          'conduction': ['load_factory_config'],
                          'when': None}}
_COND_EDGES = [('probe_factory_host', 'load_factory_config'),
 ('load_factory_config', 'select_factory_scope'),
 ('load_factory_config', 'read_factory_stuck'),
 ('load_factory_config', 'create_factory_pass_dir'),
 ('select_factory_scope', 'create_factory_pass_dir'),
 ('load_factory_config', 'build_factory_begin_state'),
 ('select_factory_scope', 'build_factory_begin_state'),
 ('read_factory_stuck', 'build_factory_begin_state'),
 ('create_factory_pass_dir', 'build_factory_begin_state'),
 ('read_factory_stuck', 'build_factory_working_state'),
 ('build_factory_working_state', 'seed_factory_occupancy'),
 ('build_factory_begin_state', 'attach_factory_stuck'),
 ('seed_factory_occupancy', 'attach_factory_stuck'),
 ('read_factory_stuck', 'attach_factory_stuck'),
 ('create_factory_pass_dir', 'persist_factory_begin_state'),
 ('attach_factory_stuck', 'persist_factory_begin_state'),
 ('create_factory_pass_dir', 'persist_factory_working_state'),
 ('attach_factory_stuck', 'persist_factory_working_state'),
 ('persist_factory_begin_state', 'persist_factory_working_state'),
 ('probe_factory_host', 'persist_factory_tick'),
 ('read_factory_stuck', 'persist_factory_tick'),
 ('create_factory_pass_dir', 'persist_factory_tick'),
 ('attach_factory_stuck', 'persist_factory_tick'),
 ('persist_factory_working_state', 'persist_factory_tick'),
 ('persist_factory_tick', 'classify_leftover_remaining'),
 ('persist_factory_tick', 'merge_leftover_remaining'),
 ('classify_leftover_remaining', 'merge_leftover_remaining')]
_WHEN_BRANCHES = []
_EFFECTORS = [{'conduction': [], 'id': 'probe_factory_host', 'when': None},
 {'conduction': ['probe_factory_host'], 'id': 'load_factory_config', 'when': None},
 {'conduction': ['load_factory_config'], 'id': 'select_factory_scope', 'when': None},
 {'conduction': ['load_factory_config'], 'id': 'read_factory_stuck', 'when': None},
 {'conduction': ['load_factory_config', 'select_factory_scope'],
  'id': 'create_factory_pass_dir',
  'when': None},
 {'conduction': ['load_factory_config',
                 'select_factory_scope',
                 'read_factory_stuck',
                 'create_factory_pass_dir'],
  'id': 'build_factory_begin_state',
  'when': None},
 {'conduction': ['read_factory_stuck'], 'id': 'build_factory_working_state', 'when': None},
 {'conduction': ['build_factory_working_state'], 'id': 'seed_factory_occupancy', 'when': None},
 {'conduction': ['build_factory_begin_state', 'seed_factory_occupancy', 'read_factory_stuck'],
  'id': 'attach_factory_stuck',
  'when': None},
 {'conduction': ['create_factory_pass_dir', 'attach_factory_stuck'],
  'id': 'persist_factory_begin_state',
  'when': None},
 {'conduction': ['create_factory_pass_dir', 'attach_factory_stuck', 'persist_factory_begin_state'],
  'id': 'persist_factory_working_state',
  'when': None},
 {'conduction': ['probe_factory_host',
                 'read_factory_stuck',
                 'create_factory_pass_dir',
                 'attach_factory_stuck',
                 'persist_factory_working_state'],
  'id': 'persist_factory_tick',
  'when': None},
 {'conduction': ['persist_factory_tick'], 'id': 'classify_leftover_remaining', 'when': None},
 {'conduction': ['persist_factory_tick', 'classify_leftover_remaining'],
  'id': 'merge_leftover_remaining',
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

