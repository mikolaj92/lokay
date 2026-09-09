"""prepare_stage_transition in stage_label_execution: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'stage_label_execution'
_NODE_ID = 'prepare_stage_transition'
_ATOM = 'prepare_stage_transition'
_CONDUCTION = []
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
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

