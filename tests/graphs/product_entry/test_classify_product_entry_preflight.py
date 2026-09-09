"""classify_product_entry_preflight in product_entry: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'product_entry'
_NODE_ID = 'classify_product_entry_preflight'
_ATOM = 'classify_product_entry_preflight'
_CONDUCTION = []
_WHEN = None
_REQUIRED_WHEN_FIELDS = ['route']
_EFFECTORS = [{'conduction': [], 'id': 'classify_product_entry_preflight', 'when': None},
 {'conduction': ['classify_product_entry_preflight'],
  'id': 'run_product_entry_budget',
  'when': {'equals': 'product', 'path': 'route', 'upstream': 'classify_product_entry_preflight'}},
 {'conduction': ['classify_product_entry_preflight', 'run_product_entry_budget'],
  'id': 'product_entry_terminal',
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

