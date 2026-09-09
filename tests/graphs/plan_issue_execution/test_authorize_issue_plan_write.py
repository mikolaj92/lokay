"""authorize_issue_plan_write in plan_issue_execution: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'plan_issue_execution'
_NODE_ID = 'authorize_issue_plan_write'
_ATOM = 'authorize_issue_plan_write'
_CONDUCTION = ['prepare_issue_plan_request', 'build_issue_approach']
_WHEN = None
_REQUIRED_WHEN_FIELDS = ['route']
_EFFECTORS = [{'conduction': [], 'id': 'prepare_issue_plan_request', 'when': None},
 {'conduction': ['prepare_issue_plan_request'], 'id': 'build_issue_approach', 'when': None},
 {'conduction': ['prepare_issue_plan_request', 'build_issue_approach'],
  'id': 'authorize_issue_plan_write',
  'when': None},
 {'conduction': ['prepare_issue_plan_request', 'build_issue_approach', 'authorize_issue_plan_write'],
  'id': 'write_issue_approach',
  'when': {'equals': 'write', 'path': 'route', 'upstream': 'authorize_issue_plan_write'}},
 {'conduction': ['authorize_issue_plan_write', 'write_issue_approach'],
  'id': 'record_issue_approach_write',
  'when': None},
 {'conduction': ['prepare_issue_plan_request',
                 'build_issue_approach',
                 'authorize_issue_plan_write',
                 'record_issue_approach_write'],
  'id': 'issue_plan_terminal',
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

