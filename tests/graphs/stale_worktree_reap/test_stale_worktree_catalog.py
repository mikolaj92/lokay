"""stale_worktree_catalog in stale_worktree_reap: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'stale_worktree_reap'
_NODE_ID = 'stale_worktree_catalog'
_ATOM = 'stale_worktree_catalog'
_CONDUCTION = ['collect_stale_worktree_candidates']
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'collect_stale_worktree_candidates', 'when': None},
 {'conduction': ['collect_stale_worktree_candidates'], 'id': 'stale_worktree_catalog', 'when': None},
 {'conduction': ['collect_stale_worktree_candidates', 'stale_worktree_catalog'],
  'id': 'summarize_stale_worktree_reap',
  'when': None}]

def test_node_identity():
    assert _NODE_ID
    assert _ATOM

def test_conduction_is_declared():
    assert isinstance(_CONDUCTION, list)

def test_required_when_fields_are_listed():
    assert all(isinstance(field, str) and field for field in _REQUIRED_WHEN_FIELDS)

def test_model_status_for_this_node():
    from support.graph_model import run_model
    status = run_model(_EFFECTORS, {})
    assert _NODE_ID in status
    assert status[_NODE_ID] in {"succeeded", "skipped"}

