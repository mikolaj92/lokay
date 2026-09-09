"""Independent conduction and when metadata for assert_real_diff_execution."""
from __future__ import annotations
import json

_PATH_ID = 'assert_real_diff_execution'
_NODES = {'classify_localized_diff_scope': {'atom': 'classify_localized_diff_scope',
                                   'conduction': ['read_real_diff_paths',
                                                  'read_real_diff_localize_scope',
                                                  'classify_ticket_scope_extra'],
                                   'when': None},
 'classify_real_diff_kind': {'atom': 'classify_real_diff_kind',
                             'conduction': ['read_real_diff_paths'],
                             'when': None},
 'classify_real_diff_progress': {'atom': 'classify_real_diff_progress',
                                 'conduction': ['classify_real_diff_kind', 'classify_localized_diff_scope'],
                                 'when': None},
 'classify_ticket_scope_extra': {'atom': 'classify_ticket_scope_extra',
                                 'conduction': ['read_real_diff_paths',
                                                'read_real_diff_issue_scope',
                                                'classify_ticket_scope_presence'],
                                 'when': None},
 'classify_ticket_scope_presence': {'atom': 'classify_ticket_scope_presence',
                                    'conduction': ['read_real_diff_paths', 'read_real_diff_issue_scope'],
                                    'when': None},
 'inspect_real_diff_worktree': {'atom': 'inspect_real_diff_worktree', 'conduction': [], 'when': None},
 'read_real_diff_issue_scope': {'atom': 'read_real_diff_issue_scope', 'conduction': [], 'when': None},
 'read_real_diff_localize_scope': {'atom': 'read_real_diff_localize_scope',
                                   'conduction': ['inspect_real_diff_worktree'],
                                   'when': None},
 'read_real_diff_paths': {'atom': 'read_real_diff_paths',
                          'conduction': ['inspect_real_diff_worktree'],
                          'when': None},
 'real_diff_terminal': {'atom': 'real_diff_terminal',
                        'conduction': ['inspect_real_diff_worktree',
                                       'read_real_diff_paths',
                                       'classify_real_diff_kind',
                                       'read_real_diff_localize_scope',
                                       'classify_ticket_scope_presence',
                                       'classify_ticket_scope_extra',
                                       'classify_localized_diff_scope',
                                       'classify_real_diff_progress'],
                        'when': None}}
_COND_EDGES = [('inspect_real_diff_worktree', 'read_real_diff_paths'),
 ('read_real_diff_paths', 'classify_real_diff_kind'),
 ('inspect_real_diff_worktree', 'read_real_diff_localize_scope'),
 ('read_real_diff_paths', 'classify_ticket_scope_presence'),
 ('read_real_diff_issue_scope', 'classify_ticket_scope_presence'),
 ('read_real_diff_paths', 'classify_ticket_scope_extra'),
 ('read_real_diff_issue_scope', 'classify_ticket_scope_extra'),
 ('classify_ticket_scope_presence', 'classify_ticket_scope_extra'),
 ('read_real_diff_paths', 'classify_localized_diff_scope'),
 ('read_real_diff_localize_scope', 'classify_localized_diff_scope'),
 ('classify_ticket_scope_extra', 'classify_localized_diff_scope'),
 ('classify_real_diff_kind', 'classify_real_diff_progress'),
 ('classify_localized_diff_scope', 'classify_real_diff_progress'),
 ('inspect_real_diff_worktree', 'real_diff_terminal'),
 ('read_real_diff_paths', 'real_diff_terminal'),
 ('classify_real_diff_kind', 'real_diff_terminal'),
 ('read_real_diff_localize_scope', 'real_diff_terminal'),
 ('classify_ticket_scope_presence', 'real_diff_terminal'),
 ('classify_ticket_scope_extra', 'real_diff_terminal'),
 ('classify_localized_diff_scope', 'real_diff_terminal'),
 ('classify_real_diff_progress', 'real_diff_terminal')]
_WHEN_BRANCHES = []
_EFFECTORS = [{'conduction': [], 'id': 'inspect_real_diff_worktree', 'when': None},
 {'conduction': ['inspect_real_diff_worktree'], 'id': 'read_real_diff_paths', 'when': None},
 {'conduction': ['read_real_diff_paths'], 'id': 'classify_real_diff_kind', 'when': None},
 {'conduction': ['inspect_real_diff_worktree'], 'id': 'read_real_diff_localize_scope', 'when': None},
 {'conduction': [], 'id': 'read_real_diff_issue_scope', 'when': None},
 {'conduction': ['read_real_diff_paths', 'read_real_diff_issue_scope'],
  'id': 'classify_ticket_scope_presence',
  'when': None},
 {'conduction': ['read_real_diff_paths', 'read_real_diff_issue_scope', 'classify_ticket_scope_presence'],
  'id': 'classify_ticket_scope_extra',
  'when': None},
 {'conduction': ['read_real_diff_paths', 'read_real_diff_localize_scope', 'classify_ticket_scope_extra'],
  'id': 'classify_localized_diff_scope',
  'when': None},
 {'conduction': ['classify_real_diff_kind', 'classify_localized_diff_scope'],
  'id': 'classify_real_diff_progress',
  'when': None},
 {'conduction': ['inspect_real_diff_worktree',
                 'read_real_diff_paths',
                 'classify_real_diff_kind',
                 'read_real_diff_localize_scope',
                 'classify_ticket_scope_presence',
                 'classify_ticket_scope_extra',
                 'classify_localized_diff_scope',
                 'classify_real_diff_progress'],
  'id': 'real_diff_terminal',
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

