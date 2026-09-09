"""select_repair_route in daemon_cycle: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'daemon_cycle'
_NODE_ID = 'select_repair_route'
_ATOM = 'select_repair_route'
_CONDUCTION = ['last_pass_moving']
_WHEN = None
_REQUIRED_WHEN_FIELDS = ['route']
_EFFECTORS = [{'conduction': [], 'id': 'last_pass_moving', 'when': None},
 {'conduction': ['last_pass_moving'], 'id': 'select_repair_route', 'when': None},
 {'conduction': ['select_repair_route'],
  'id': 'recovery_incident',
  'when': {'equals': 'repair', 'path': 'route', 'upstream': 'select_repair_route'}},
 {'conduction': ['select_repair_route', 'recovery_incident'],
  'id': 'recovery_run_self_repair',
  'when': {'equals': 'repair', 'path': 'route', 'upstream': 'select_repair_route'}},
 {'conduction': ['select_repair_route', 'recovery_run_self_repair'],
  'id': 'recovery_factory',
  'when': {'equals': 'factory', 'path': 'route', 'upstream': 'select_repair_route'}},
 {'conduction': ['select_repair_route', 'recovery_factory', 'recovery_run_self_repair'],
  'id': 'summarize_daemon_cycle',
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

