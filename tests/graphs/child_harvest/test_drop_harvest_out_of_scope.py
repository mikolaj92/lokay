"""drop_harvest_out_of_scope in child_harvest: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'child_harvest'
_NODE_ID = 'drop_harvest_out_of_scope'
_ATOM = 'drop_harvest_out_of_scope'
_CONDUCTION = ['clear_harvest_closed_rows']
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'collect_child_harvest_facts', 'when': None},
 {'conduction': ['collect_child_harvest_facts'], 'id': 'reconcile_dead_child_receipts', 'when': None},
 {'conduction': ['reconcile_dead_child_receipts'], 'id': 'reconcile_harvest_journal_misses', 'when': None},
 {'conduction': ['reconcile_harvest_journal_misses'], 'id': 'reconcile_harvest_deliveries', 'when': None},
 {'conduction': ['reconcile_harvest_deliveries'], 'id': 'reconcile_harvest_blocked_misses', 'when': None},
 {'conduction': ['reconcile_harvest_blocked_misses'], 'id': 'harvest_catalog', 'when': None},
 {'conduction': ['harvest_catalog'], 'id': 'clear_harvest_closed_rows', 'when': None},
 {'conduction': ['clear_harvest_closed_rows'], 'id': 'drop_harvest_out_of_scope', 'when': None},
 {'conduction': ['drop_harvest_out_of_scope'], 'id': 'clear_harvest_cycle_starts', 'when': None},
 {'conduction': ['clear_harvest_cycle_starts'], 'id': 'child_harvest_terminal', 'when': None}]

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

