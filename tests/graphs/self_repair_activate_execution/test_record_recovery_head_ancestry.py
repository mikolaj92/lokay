"""record_recovery_head_ancestry in self_repair_activate_execution: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'self_repair_activate_execution'
_NODE_ID = 'record_recovery_head_ancestry'
_ATOM = 'record_recovery_head_ancestry'
_CONDUCTION = ['classify_activated_head', 'check_recovery_ancestor_head']
_WHEN = None
_REQUIRED_WHEN_FIELDS = ['route']
_EFFECTORS = [{'conduction': [], 'id': 'prepare_self_repair_activation', 'when': None},
 {'conduction': ['prepare_self_repair_activation'],
  'id': 'read_canonical_checkout_status',
  'when': {'equals': 'status', 'path': 'route', 'upstream': 'prepare_self_repair_activation'}},
 {'conduction': ['prepare_self_repair_activation', 'read_canonical_checkout_status'],
  'id': 'classify_canonical_checkout',
  'when': None},
 {'conduction': ['prepare_self_repair_activation', 'classify_canonical_checkout'],
  'id': 'check_dirty_commit_on_origin',
  'when': {'equals': 'dirty', 'path': 'route', 'upstream': 'classify_canonical_checkout'}},
 {'conduction': ['prepare_self_repair_activation', 'classify_canonical_checkout'],
  'id': 'fetch_canonical_main',
  'when': {'equals': 'clean', 'path': 'route', 'upstream': 'classify_canonical_checkout'}},
 {'conduction': ['classify_canonical_checkout', 'fetch_canonical_main'],
  'id': 'record_canonical_fetch',
  'when': None},
 {'conduction': ['prepare_self_repair_activation', 'record_canonical_fetch'],
  'id': 'fast_forward_recovery_commit',
  'when': {'equals': 'fetched', 'path': 'route', 'upstream': 'record_canonical_fetch'}},
 {'conduction': ['record_canonical_fetch', 'fast_forward_recovery_commit'],
  'id': 'record_recovery_fast_forward',
  'when': None},
 {'conduction': ['prepare_self_repair_activation', 'record_recovery_fast_forward'],
  'id': 'read_activated_head',
  'when': {'equals': 'merged', 'path': 'route', 'upstream': 'record_recovery_fast_forward'}},
 {'conduction': ['prepare_self_repair_activation',
                 'classify_canonical_checkout',
                 'check_dirty_commit_on_origin',
                 'record_canonical_fetch',
                 'record_recovery_fast_forward',
                 'read_activated_head'],
  'id': 'classify_activated_head',
  'when': None},
 {'conduction': ['prepare_self_repair_activation', 'classify_activated_head'],
  'id': 'check_recovery_ancestor_head',
  'when': {'equals': 'ancestry', 'path': 'route', 'upstream': 'classify_activated_head'}},
 {'conduction': ['classify_activated_head', 'check_recovery_ancestor_head'],
  'id': 'record_recovery_head_ancestry',
  'when': None},
 {'conduction': ['prepare_self_repair_activation',
                 'classify_activated_head',
                 'record_recovery_head_ancestry'],
  'id': 'check_recovery_ancestor_origin',
  'when': {'equals': 'not_ancestor', 'path': 'route', 'upstream': 'record_recovery_head_ancestry'}},
 {'conduction': ['prepare_self_repair_activation',
                 'classify_canonical_checkout',
                 'check_dirty_commit_on_origin',
                 'record_canonical_fetch',
                 'record_recovery_fast_forward',
                 'read_activated_head',
                 'classify_activated_head',
                 'record_recovery_head_ancestry',
                 'check_recovery_ancestor_origin'],
  'id': 'self_repair_activation_terminal',
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

