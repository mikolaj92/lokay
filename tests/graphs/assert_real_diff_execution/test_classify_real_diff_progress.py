"""classify_real_diff_progress in assert_real_diff_execution: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'assert_real_diff_execution'
_NODE_ID = 'classify_real_diff_progress'
_ATOM = 'classify_real_diff_progress'
_CONDUCTION = ['classify_real_diff_kind', 'classify_localized_diff_scope']
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
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

