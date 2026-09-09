"""Independent conduction and when metadata for stale_worktree_reap."""
from __future__ import annotations
import json

_PATH_ID = 'stale_worktree_reap'
_NODES = {'collect_stale_worktree_candidates': {'atom': 'collect_stale_worktree_candidates',
                                       'conduction': [],
                                       'when': None},
 'stale_worktree_catalog': {'atom': 'stale_worktree_catalog',
                            'conduction': ['collect_stale_worktree_candidates'],
                            'when': None},
 'summarize_stale_worktree_reap': {'atom': 'summarize_stale_worktree_reap',
                                   'conduction': ['collect_stale_worktree_candidates',
                                                  'stale_worktree_catalog'],
                                   'when': None}}
_COND_EDGES = [('collect_stale_worktree_candidates', 'stale_worktree_catalog'),
 ('collect_stale_worktree_candidates', 'summarize_stale_worktree_reap'),
 ('stale_worktree_catalog', 'summarize_stale_worktree_reap')]
_WHEN_BRANCHES = []
_EFFECTORS = [{'conduction': [], 'id': 'collect_stale_worktree_candidates', 'when': None},
 {'conduction': ['collect_stale_worktree_candidates'], 'id': 'stale_worktree_catalog', 'when': None},
 {'conduction': ['collect_stale_worktree_candidates', 'stale_worktree_catalog'],
  'id': 'summarize_stale_worktree_reap',
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

