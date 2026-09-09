"""Independent conduction and when metadata for child_harvest."""
from __future__ import annotations
import json

_PATH_ID = 'child_harvest'
_NODES = {'child_harvest_terminal': {'atom': 'child_harvest_terminal',
                            'conduction': ['clear_harvest_cycle_starts'],
                            'when': None},
 'clear_harvest_closed_rows': {'atom': 'clear_harvest_closed_rows',
                               'conduction': ['harvest_catalog'],
                               'when': None},
 'clear_harvest_cycle_starts': {'atom': 'clear_harvest_cycle_starts',
                                'conduction': ['drop_harvest_out_of_scope'],
                                'when': None},
 'collect_child_harvest_facts': {'atom': 'collect_child_harvest_facts', 'conduction': [], 'when': None},
 'drop_harvest_out_of_scope': {'atom': 'drop_harvest_out_of_scope',
                               'conduction': ['clear_harvest_closed_rows'],
                               'when': None},
 'harvest_catalog': {'atom': 'harvest_catalog',
                     'conduction': ['reconcile_harvest_blocked_misses'],
                     'when': None},
 'reconcile_dead_child_receipts': {'atom': 'reconcile_dead_child_receipts',
                                   'conduction': ['collect_child_harvest_facts'],
                                   'when': None},
 'reconcile_harvest_blocked_misses': {'atom': 'reconcile_harvest_blocked_misses',
                                      'conduction': ['reconcile_harvest_deliveries'],
                                      'when': None},
 'reconcile_harvest_deliveries': {'atom': 'reconcile_harvest_deliveries',
                                  'conduction': ['reconcile_harvest_journal_misses'],
                                  'when': None},
 'reconcile_harvest_journal_misses': {'atom': 'reconcile_harvest_journal_misses',
                                      'conduction': ['reconcile_dead_child_receipts'],
                                      'when': None}}
_COND_EDGES = [('collect_child_harvest_facts', 'reconcile_dead_child_receipts'),
 ('reconcile_dead_child_receipts', 'reconcile_harvest_journal_misses'),
 ('reconcile_harvest_journal_misses', 'reconcile_harvest_deliveries'),
 ('reconcile_harvest_deliveries', 'reconcile_harvest_blocked_misses'),
 ('reconcile_harvest_blocked_misses', 'harvest_catalog'),
 ('harvest_catalog', 'clear_harvest_closed_rows'),
 ('clear_harvest_closed_rows', 'drop_harvest_out_of_scope'),
 ('drop_harvest_out_of_scope', 'clear_harvest_cycle_starts'),
 ('clear_harvest_cycle_starts', 'child_harvest_terminal')]
_WHEN_BRANCHES = []
_EFFECTORS = [{'conduction': [], 'id': 'collect_child_harvest_facts', 'when': None},
 {'conduction': ['collect_child_harvest_facts'], 'id': 'reconcile_dead_child_receipts', 'when': None},
 {'conduction': ['reconcile_dead_child_receipts'], 'id': 'reconcile_harvest_journal_misses', 'when': None},
 {'conduction': ['reconcile_harvest_journal_misses'], 'id': 'reconcile_harvest_deliveries', 'when': None},
 {'conduction': ['reconcile_harvest_deliveries'], 'id': 'reconcile_harvest_blocked_misses', 'when': None},
 {'conduction': ['reconcile_harvest_blocked_misses'], 'id': 'harvest_catalog', 'when': None},
 {'conduction': ['harvest_catalog'], 'id': 'clear_harvest_closed_rows', 'when': None},
 {'conduction': ['clear_harvest_closed_rows'], 'id': 'drop_harvest_out_of_scope', 'when': None},
 {'conduction': ['drop_harvest_out_of_scope'], 'id': 'clear_harvest_cycle_starts', 'when': None},
 {'conduction': ['clear_harvest_cycle_starts'], 'id': 'child_harvest_terminal', 'when': None}]

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

