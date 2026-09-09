"""classify_pr_create_issue in pr_create_execution: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'pr_create_execution'
_NODE_ID = 'classify_pr_create_issue'
_ATOM = 'classify_pr_create_issue'
_CONDUCTION = ['record_existing_delivery_pr', 'read_pr_create_issue']
_WHEN = None
_REQUIRED_WHEN_FIELDS = ['route']
_EFFECTORS = [{'conduction': [], 'id': 'prepare_pr_create_request', 'when': None},
 {'conduction': ['prepare_pr_create_request'], 'id': 'find_existing_delivery_pr', 'when': None},
 {'conduction': ['find_existing_delivery_pr'], 'id': 'record_existing_delivery_pr', 'when': None},
 {'conduction': ['prepare_pr_create_request', 'record_existing_delivery_pr'],
  'id': 'read_pr_create_issue',
  'when': {'equals': 'none', 'path': 'route', 'upstream': 'record_existing_delivery_pr'}},
 {'conduction': ['record_existing_delivery_pr', 'read_pr_create_issue'],
  'id': 'classify_pr_create_issue',
  'when': None},
 {'conduction': ['prepare_pr_create_request', 'classify_pr_create_issue'],
  'id': 'create_pull_request_effect',
  'when': {'equals': 'create', 'path': 'route', 'upstream': 'classify_pr_create_issue'}},
 {'conduction': ['prepare_pr_create_request',
                 'record_existing_delivery_pr',
                 'read_pr_create_issue',
                 'classify_pr_create_issue',
                 'create_pull_request_effect'],
  'id': 'pr_create_terminal',
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

