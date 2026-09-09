"""Independent conduction and when metadata for issue_to_pr."""
from __future__ import annotations
import json

_PATH_ID = 'issue_to_pr'
_NODES = {'close_existing_delivery': {'atom': 'close_existing_delivery',
                             'conduction': ['get_issue', 'resolve_existing_delivery'],
                             'when': {'equals': 'closeout',
                                      'path': 'route',
                                      'upstream': 'resolve_existing_delivery'}},
 'collect_existing_delivery_pr': {'atom': 'collect_existing_delivery_pr',
                                  'conduction': ['get_issue', 'resolve_implementation_issue'],
                                  'when': None},
 'collect_resumed_source': {'atom': 'collect_resumed_source',
                            'conduction': ['get_issue', 'resolve_implementation_issue'],
                            'when': None},
 'get_issue': {'atom': 'get_issue', 'conduction': [], 'when': None},
 'issue_to_pr_no_effect': {'atom': 'issue_to_pr_no_effect',
                           'conduction': ['resolve_existing_delivery'],
                           'when': {'equals': 'no_effect',
                                    'path': 'route',
                                    'upstream': 'resolve_existing_delivery'}},
 'issue_to_pr_subflow': {'atom': 'issue_to_pr_subflow',
                         'conduction': ['get_issue', 'resolve_existing_delivery'],
                         'when': {'equals': 'deliver',
                                  'path': 'route',
                                  'upstream': 'resolve_existing_delivery'}},
 'resolve_existing_delivery': {'atom': 'resolve_existing_delivery',
                               'conduction': ['resolve_implementation_issue',
                                              'collect_existing_delivery_pr',
                                              'collect_resumed_source'],
                               'when': None},
 'resolve_implementation_issue': {'atom': 'resolve_implementation_issue',
                                  'conduction': ['get_issue'],
                                  'when': None},
 'summarize_issue_to_pr': {'atom': 'summarize_issue_to_pr',
                           'conduction': ['resolve_existing_delivery',
                                          'issue_to_pr_subflow',
                                          'close_existing_delivery',
                                          'issue_to_pr_no_effect'],
                           'when': None}}
_COND_EDGES = [('get_issue', 'resolve_implementation_issue'),
 ('get_issue', 'collect_existing_delivery_pr'),
 ('resolve_implementation_issue', 'collect_existing_delivery_pr'),
 ('get_issue', 'collect_resumed_source'),
 ('resolve_implementation_issue', 'collect_resumed_source'),
 ('resolve_implementation_issue', 'resolve_existing_delivery'),
 ('collect_existing_delivery_pr', 'resolve_existing_delivery'),
 ('collect_resumed_source', 'resolve_existing_delivery'),
 ('get_issue', 'issue_to_pr_subflow'),
 ('resolve_existing_delivery', 'issue_to_pr_subflow'),
 ('get_issue', 'close_existing_delivery'),
 ('resolve_existing_delivery', 'close_existing_delivery'),
 ('resolve_existing_delivery', 'issue_to_pr_no_effect'),
 ('resolve_existing_delivery', 'summarize_issue_to_pr'),
 ('issue_to_pr_subflow', 'summarize_issue_to_pr'),
 ('close_existing_delivery', 'summarize_issue_to_pr'),
 ('issue_to_pr_no_effect', 'summarize_issue_to_pr')]
_WHEN_BRANCHES = [('issue_to_pr_subflow', {'equals': 'deliver', 'path': 'route', 'upstream': 'resolve_existing_delivery'}),
 ('close_existing_delivery',
  {'equals': 'closeout', 'path': 'route', 'upstream': 'resolve_existing_delivery'}),
 ('issue_to_pr_no_effect', {'equals': 'no_effect', 'path': 'route', 'upstream': 'resolve_existing_delivery'})]
_EFFECTORS = [{'conduction': [], 'id': 'get_issue', 'when': None},
 {'conduction': ['get_issue'], 'id': 'resolve_implementation_issue', 'when': None},
 {'conduction': ['get_issue', 'resolve_implementation_issue'],
  'id': 'collect_existing_delivery_pr',
  'when': None},
 {'conduction': ['get_issue', 'resolve_implementation_issue'], 'id': 'collect_resumed_source', 'when': None},
 {'conduction': ['resolve_implementation_issue', 'collect_existing_delivery_pr', 'collect_resumed_source'],
  'id': 'resolve_existing_delivery',
  'when': None},
 {'conduction': ['get_issue', 'resolve_existing_delivery'],
  'id': 'issue_to_pr_subflow',
  'when': {'equals': 'deliver', 'path': 'route', 'upstream': 'resolve_existing_delivery'}},
 {'conduction': ['get_issue', 'resolve_existing_delivery'],
  'id': 'close_existing_delivery',
  'when': {'equals': 'closeout', 'path': 'route', 'upstream': 'resolve_existing_delivery'}},
 {'conduction': ['resolve_existing_delivery'],
  'id': 'issue_to_pr_no_effect',
  'when': {'equals': 'no_effect', 'path': 'route', 'upstream': 'resolve_existing_delivery'}},
 {'conduction': ['resolve_existing_delivery',
                 'issue_to_pr_subflow',
                 'close_existing_delivery',
                 'issue_to_pr_no_effect'],
  'id': 'summarize_issue_to_pr',
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

