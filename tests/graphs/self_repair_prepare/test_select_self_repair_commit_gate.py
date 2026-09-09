"""select_self_repair_commit_gate in self_repair_prepare: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'self_repair_prepare'
_NODE_ID = 'select_self_repair_commit_gate'
_ATOM = 'select_self_repair_commit_gate'
_CONDUCTION = ['select_self_repair_shape_gate', 'inspect_self_repair_commit']
_WHEN = None
_REQUIRED_WHEN_FIELDS = ['route']
_EFFECTORS = [{'conduction': [], 'id': 'resolve_self_repair_checkout', 'when': None},
 {'conduction': ['resolve_self_repair_checkout'], 'id': 'check_self_repair_mutation_gate', 'when': None},
 {'conduction': ['check_self_repair_mutation_gate'],
  'id': 'verify_self_repair_origin',
  'when': {'equals': 'live', 'path': 'route', 'upstream': 'check_self_repair_mutation_gate'}},
 {'conduction': ['check_self_repair_mutation_gate', 'verify_self_repair_origin'],
  'id': 'select_self_repair_origin_gate',
  'when': None},
 {'conduction': ['select_self_repair_origin_gate'],
  'id': 'fetch_self_repair_main',
  'when': {'equals': 'verified', 'path': 'route', 'upstream': 'select_self_repair_origin_gate'}},
 {'conduction': ['select_self_repair_origin_gate', 'fetch_self_repair_main'],
  'id': 'select_self_repair_fetch_gate',
  'when': None},
 {'conduction': ['select_self_repair_fetch_gate'],
  'id': 'find_published_self_repair',
  'when': {'equals': 'fetched', 'path': 'route', 'upstream': 'select_self_repair_fetch_gate'}},
 {'conduction': ['check_self_repair_mutation_gate',
                 'select_self_repair_fetch_gate',
                 'find_published_self_repair'],
  'id': 'select_self_repair_publish_gate',
  'when': None},
 {'conduction': ['select_self_repair_publish_gate'],
  'id': 'read_self_repair_base',
  'when': {'equals': 'unpublished', 'path': 'route', 'upstream': 'select_self_repair_publish_gate'}},
 {'conduction': ['select_self_repair_publish_gate', 'read_self_repair_base'],
  'id': 'select_self_repair_base_gate',
  'when': None},
 {'conduction': ['select_self_repair_base_gate'],
  'id': 'inspect_self_repair_ownership',
  'when': {'equals': 'inspect', 'path': 'route', 'upstream': 'select_self_repair_base_gate'}},
 {'conduction': ['select_self_repair_base_gate', 'inspect_self_repair_ownership'],
  'id': 'select_self_repair_ownership_gate',
  'when': None},
 {'conduction': ['select_self_repair_ownership_gate'],
  'id': 'inspect_self_repair_changes',
  'when': {'equals': 'owned', 'path': 'route', 'upstream': 'select_self_repair_ownership_gate'}},
 {'conduction': ['select_self_repair_ownership_gate', 'inspect_self_repair_changes'],
  'id': 'select_self_repair_changes_gate',
  'when': None},
 {'conduction': ['select_self_repair_changes_gate'],
  'id': 'validate_self_repair_change_shape',
  'when': {'equals': 'changes', 'path': 'route', 'upstream': 'select_self_repair_changes_gate'}},
 {'conduction': ['select_self_repair_changes_gate', 'validate_self_repair_change_shape'],
  'id': 'select_self_repair_shape_gate',
  'when': None},
 {'conduction': ['select_self_repair_shape_gate'],
  'id': 'inspect_self_repair_commit',
  'when': {'equals': 'commit_facts', 'path': 'route', 'upstream': 'select_self_repair_shape_gate'}},
 {'conduction': ['select_self_repair_shape_gate', 'inspect_self_repair_commit'],
  'id': 'select_self_repair_commit_gate',
  'when': None},
 {'conduction': ['select_self_repair_commit_gate'],
  'id': 'validate_self_repair_commit',
  'when': {'equals': 'commit', 'path': 'route', 'upstream': 'select_self_repair_commit_gate'}},
 {'conduction': ['select_self_repair_commit_gate', 'validate_self_repair_commit'],
  'id': 'select_self_repair_commit_validation_gate',
  'when': None},
 {'conduction': ['select_self_repair_commit_validation_gate'],
  'id': 'inspect_self_repair_ancestry',
  'when': {'equals': 'ancestry', 'path': 'route', 'upstream': 'select_self_repair_commit_validation_gate'}},
 {'conduction': ['select_self_repair_base_gate',
                 'select_self_repair_ownership_gate',
                 'select_self_repair_changes_gate',
                 'select_self_repair_shape_gate',
                 'select_self_repair_commit_validation_gate',
                 'inspect_self_repair_ancestry'],
  'id': 'select_self_repair_worktree_route',
  'when': None},
 {'conduction': ['select_self_repair_worktree_route'],
  'id': 'remove_self_repair_worktree',
  'when': {'equals': 'remove', 'path': 'route', 'upstream': 'select_self_repair_worktree_route'}},
 {'conduction': ['select_self_repair_worktree_route', 'remove_self_repair_worktree'],
  'id': 'select_self_repair_remove_outcome',
  'when': None},
 {'conduction': ['select_self_repair_remove_outcome'],
  'id': 'create_self_repair_worktree',
  'when': {'equals': 'create_requested', 'path': 'route', 'upstream': 'select_self_repair_remove_outcome'}},
 {'conduction': ['resolve_self_repair_checkout',
                 'check_self_repair_mutation_gate',
                 'select_self_repair_publish_gate',
                 'select_self_repair_base_gate',
                 'select_self_repair_worktree_route',
                 'select_self_repair_remove_outcome',
                 'create_self_repair_worktree'],
  'id': 'select_self_repair_prepare_result',
  'when': None},
 {'conduction': ['select_self_repair_prepare_result'], 'id': 'summarize_self_repair_prepare', 'when': None}]

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

def test_required_when_fields_live_on_domain_output():
    values = {"ok": True, "atom": _ATOM}
    for field in _REQUIRED_WHEN_FIELDS:
        if "." in field:
            current = values
            parts = field.split(".")
            for part in parts[:-1]:
                current = current.setdefault(part, {})
            current.setdefault(parts[-1], "value")
        else:
            values.setdefault(field, "value")
    from support.graph_model import lookup_path
    for field in _REQUIRED_WHEN_FIELDS:
        found, _ = lookup_path(values, field)
        assert found, field

