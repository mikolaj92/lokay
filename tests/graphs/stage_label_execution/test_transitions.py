"""Independent conduction and when metadata for stage_label_execution."""
from __future__ import annotations
import json

_PATH_ID = 'stage_label_execution'
_NODES = {'add_stage_labels_effect': {'atom': 'add_stage_labels_effect',
                             'conduction': ['prepare_stage_transition', 'record_stage_removal'],
                             'when': None},
 'classify_stage_issue': {'atom': 'classify_stage_issue',
                          'conduction': ['prepare_stage_transition', 'read_stage_issue'],
                          'when': None},
 'comment_stage_receipt_effect': {'atom': 'comment_stage_receipt_effect',
                                  'conduction': ['prepare_stage_transition', 'add_stage_labels_effect'],
                                  'when': {'equals': 'comment',
                                           'path': 'route',
                                           'upstream': 'add_stage_labels_effect'}},
 'prepare_stage_transition': {'atom': 'prepare_stage_transition', 'conduction': [], 'when': None},
 'read_stage_issue': {'atom': 'read_stage_issue', 'conduction': ['prepare_stage_transition'], 'when': None},
 'record_stage_removal': {'atom': 'record_stage_removal',
                          'conduction': ['classify_stage_issue', 'remove_stage_labels_effect'],
                          'when': None},
 'remove_stage_labels_effect': {'atom': 'remove_stage_labels_effect',
                                'conduction': ['prepare_stage_transition', 'classify_stage_issue'],
                                'when': {'equals': 'remove',
                                         'path': 'route',
                                         'upstream': 'classify_stage_issue'}},
 'stage_label_terminal': {'atom': 'stage_label_terminal',
                          'conduction': ['prepare_stage_transition',
                                         'read_stage_issue',
                                         'classify_stage_issue',
                                         'record_stage_removal',
                                         'add_stage_labels_effect',
                                         'comment_stage_receipt_effect'],
                          'when': None}}
_COND_EDGES = [('prepare_stage_transition', 'read_stage_issue'),
 ('prepare_stage_transition', 'classify_stage_issue'),
 ('read_stage_issue', 'classify_stage_issue'),
 ('prepare_stage_transition', 'remove_stage_labels_effect'),
 ('classify_stage_issue', 'remove_stage_labels_effect'),
 ('classify_stage_issue', 'record_stage_removal'),
 ('remove_stage_labels_effect', 'record_stage_removal'),
 ('prepare_stage_transition', 'add_stage_labels_effect'),
 ('record_stage_removal', 'add_stage_labels_effect'),
 ('prepare_stage_transition', 'comment_stage_receipt_effect'),
 ('add_stage_labels_effect', 'comment_stage_receipt_effect'),
 ('prepare_stage_transition', 'stage_label_terminal'),
 ('read_stage_issue', 'stage_label_terminal'),
 ('classify_stage_issue', 'stage_label_terminal'),
 ('record_stage_removal', 'stage_label_terminal'),
 ('add_stage_labels_effect', 'stage_label_terminal'),
 ('comment_stage_receipt_effect', 'stage_label_terminal')]
_WHEN_BRANCHES = [('remove_stage_labels_effect', {'equals': 'remove', 'path': 'route', 'upstream': 'classify_stage_issue'}),
 ('comment_stage_receipt_effect',
  {'equals': 'comment', 'path': 'route', 'upstream': 'add_stage_labels_effect'})]
_EFFECTORS = [{'conduction': [], 'id': 'prepare_stage_transition', 'when': None},
 {'conduction': ['prepare_stage_transition'], 'id': 'read_stage_issue', 'when': None},
 {'conduction': ['prepare_stage_transition', 'read_stage_issue'], 'id': 'classify_stage_issue', 'when': None},
 {'conduction': ['prepare_stage_transition', 'classify_stage_issue'],
  'id': 'remove_stage_labels_effect',
  'when': {'equals': 'remove', 'path': 'route', 'upstream': 'classify_stage_issue'}},
 {'conduction': ['classify_stage_issue', 'remove_stage_labels_effect'],
  'id': 'record_stage_removal',
  'when': None},
 {'conduction': ['prepare_stage_transition', 'record_stage_removal'],
  'id': 'add_stage_labels_effect',
  'when': None},
 {'conduction': ['prepare_stage_transition', 'add_stage_labels_effect'],
  'id': 'comment_stage_receipt_effect',
  'when': {'equals': 'comment', 'path': 'route', 'upstream': 'add_stage_labels_effect'}},
 {'conduction': ['prepare_stage_transition',
                 'read_stage_issue',
                 'classify_stage_issue',
                 'record_stage_removal',
                 'add_stage_labels_effect',
                 'comment_stage_receipt_effect'],
  'id': 'stage_label_terminal',
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

