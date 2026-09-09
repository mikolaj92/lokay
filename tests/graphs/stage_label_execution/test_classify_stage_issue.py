"""classify_stage_issue in stage_label_execution: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'stage_label_execution'
_NODE_ID = 'classify_stage_issue'
_ATOM = 'classify_stage_issue'
_CONDUCTION = ['prepare_stage_transition', 'read_stage_issue']
_WHEN = None
_REQUIRED_WHEN_FIELDS = ['route']
_EFFECTORS = [{'conduction': [], 'id': 'prepare_stage_transition', 'when': None},
 {'conduction': ['prepare_stage_transition'], 'id': 'read_stage_issue', 'when': None},
 {'conduction': ['prepare_stage_transition', 'read_stage_issue'], 'id': 'classify_stage_issue', 'when': None},
 {'conduction': ['prepare_stage_transition', 'classify_stage_issue'],
  'id': 'remove_stage_labels_effect',
  'when': {'equals': 'remove', 'path': 'route', 'upstream': 'classify_stage_issue'}},
 {'conduction': ['classify_stage_issue', 'remove_stage_labels_effect'],
  'id': 'record_stage_removal',
  'when': None},
 {'conduction': ['prepare_stage_transition', 'record_stage_removal'],
  'id': 'add_stage_labels_effect',
  'when': None},
 {'conduction': ['prepare_stage_transition', 'add_stage_labels_effect'],
  'id': 'comment_stage_receipt_effect',
  'when': {'equals': 'comment', 'path': 'route', 'upstream': 'add_stage_labels_effect'}},
 {'conduction': ['prepare_stage_transition',
                 'read_stage_issue',
                 'classify_stage_issue',
                 'record_stage_removal',
                 'add_stage_labels_effect',
                 'comment_stage_receipt_effect'],
  'id': 'stage_label_terminal',
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

