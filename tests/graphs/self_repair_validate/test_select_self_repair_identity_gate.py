"""select_self_repair_identity_gate in self_repair_validate: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'self_repair_validate'
_NODE_ID = 'select_self_repair_identity_gate'
_ATOM = 'select_self_repair_identity_gate'
_CONDUCTION = ['validate_self_repair_identity_request', 'inspect_self_repair_candidate_identity']
_WHEN = None
_REQUIRED_WHEN_FIELDS = ['route']
_EFFECTORS = [{'conduction': [], 'id': 'read_self_repair_candidate_state', 'when': None},
 {'conduction': ['read_self_repair_candidate_state'],
  'id': 'classify_self_repair_candidate_diff',
  'when': None},
 {'conduction': ['classify_self_repair_candidate_diff'],
  'id': 'validate_self_repair_identity_request',
  'when': None},
 {'conduction': ['validate_self_repair_identity_request'],
  'id': 'inspect_self_repair_candidate_identity',
  'when': {'equals': 'inspect', 'path': 'route', 'upstream': 'validate_self_repair_identity_request'}},
 {'conduction': ['validate_self_repair_identity_request', 'inspect_self_repair_candidate_identity'],
  'id': 'select_self_repair_identity_gate',
  'when': None},
 {'conduction': ['select_self_repair_identity_gate'],
  'id': 'verify_self_repair_candidate_identity',
  'when': {'equals': 'identity', 'path': 'route', 'upstream': 'select_self_repair_identity_gate'}},
 {'conduction': ['select_self_repair_identity_gate', 'verify_self_repair_candidate_identity'],
  'id': 'run_self_repair_tests',
  'when': None},
 {'conduction': ['run_self_repair_tests'],
  'id': 'list_self_repair_untracked_paths',
  'when': {'equals': True, 'path': 'ok', 'upstream': 'run_self_repair_tests'}},
 {'conduction': ['list_self_repair_untracked_paths'],
  'id': 'self_repair_untracked_catalog',
  'when': {'equals': True, 'path': 'ok', 'upstream': 'list_self_repair_untracked_paths'}},
 {'conduction': ['self_repair_untracked_catalog'],
  'id': 'check_self_repair_tracked_working',
  'when': {'equals': True, 'path': 'ok', 'upstream': 'self_repair_untracked_catalog'}},
 {'conduction': ['check_self_repair_tracked_working'],
  'id': 'check_self_repair_tracked_cached',
  'when': {'equals': True, 'path': 'ok', 'upstream': 'check_self_repair_tracked_working'}},
 {'conduction': ['check_self_repair_tracked_cached'],
  'id': 'select_self_repair_committed_need',
  'when': {'equals': True, 'path': 'ok', 'upstream': 'check_self_repair_tracked_cached'}},
 {'conduction': ['select_self_repair_committed_need'],
  'id': 'check_self_repair_tracked_committed',
  'when': {'equals': 'has_base', 'path': 'route', 'upstream': 'select_self_repair_committed_need'}},
 {'conduction': ['check_self_repair_tracked_cached', 'check_self_repair_tracked_committed'],
  'id': 'select_self_repair_committed_gate',
  'when': {'equals': True, 'path': 'ok', 'upstream': 'check_self_repair_tracked_cached'}},
 {'conduction': ['select_self_repair_committed_gate'],
  'id': 'recheck_self_repair_identity',
  'when': {'equals': True, 'path': 'ok', 'upstream': 'select_self_repair_committed_gate'}},
 {'conduction': ['recheck_self_repair_identity'],
  'id': 'summarize_self_repair_validation',
  'when': {'equals': True, 'path': 'ok', 'upstream': 'recheck_self_repair_identity'}}]

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

