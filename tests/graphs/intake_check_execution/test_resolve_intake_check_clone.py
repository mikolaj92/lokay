"""resolve_intake_check_clone in intake_check_execution: geometry and required when fields."""
from __future__ import annotations

_PATH_ID = 'intake_check_execution'
_NODE_ID = 'resolve_intake_check_clone'
_ATOM = 'resolve_intake_check_clone'
_CONDUCTION = ['prepare_intake_check', 'read_intake_check_issue']
_WHEN = None
_REQUIRED_WHEN_FIELDS = []
_EFFECTORS = [{'conduction': [], 'id': 'prepare_intake_check', 'when': None},
 {'conduction': ['prepare_intake_check'], 'id': 'read_intake_check_issue', 'when': None},
 {'conduction': ['prepare_intake_check', 'read_intake_check_issue'],
  'id': 'resolve_intake_check_clone',
  'when': None},
 {'conduction': ['prepare_intake_check', 'read_intake_check_issue'],
  'id': 'classify_intake_check_route',
  'when': None},
 {'conduction': ['read_intake_check_issue', 'classify_intake_check_route'],
  'id': 'run_intake_open_check',
  'when': {'equals': 'open', 'path': 'route', 'upstream': 'classify_intake_check_route'}},
 {'conduction': ['prepare_intake_check', 'read_intake_check_issue', 'classify_intake_check_route'],
  'id': 'run_intake_superseded_check',
  'when': {'equals': 'superseded', 'path': 'route', 'upstream': 'classify_intake_check_route'}},
 {'conduction': ['resolve_intake_check_clone', 'classify_intake_check_route'],
  'id': 'probe_intake_check_shape',
  'when': {'equals': 'shape', 'path': 'route', 'upstream': 'classify_intake_check_route'}},
 {'conduction': ['read_intake_check_issue', 'probe_intake_check_shape', 'classify_intake_check_route'],
  'id': 'run_intake_shape_check',
  'when': {'equals': 'shape', 'path': 'route', 'upstream': 'classify_intake_check_route'}},
 {'conduction': ['read_intake_check_issue', 'resolve_intake_check_clone', 'classify_intake_check_route'],
  'id': 'run_intake_satisfied_check',
  'when': {'equals': 'satisfied', 'path': 'route', 'upstream': 'classify_intake_check_route'}},
 {'conduction': ['read_intake_check_issue', 'classify_intake_check_route'],
  'id': 'run_intake_ambiguity_check',
  'when': {'equals': 'ambiguity', 'path': 'route', 'upstream': 'classify_intake_check_route'}},
 {'conduction': ['prepare_intake_check', 'classify_intake_check_route'],
  'id': 'parse_intake_covering_prs',
  'when': {'equals': 'duplicate_ai_pr', 'path': 'route', 'upstream': 'classify_intake_check_route'}},
 {'conduction': ['read_intake_check_issue', 'parse_intake_covering_prs', 'classify_intake_check_route'],
  'id': 'run_intake_duplicate_pr_check',
  'when': {'equals': 'duplicate_ai_pr', 'path': 'route', 'upstream': 'classify_intake_check_route'}},
 {'conduction': ['run_intake_open_check',
                 'run_intake_superseded_check',
                 'run_intake_shape_check',
                 'run_intake_satisfied_check',
                 'run_intake_ambiguity_check',
                 'run_intake_duplicate_pr_check',
                 'parse_intake_covering_prs'],
  'id': 'select_intake_check_result',
  'when': None},
 {'conduction': ['prepare_intake_check',
                 'read_intake_check_issue',
                 'resolve_intake_check_clone',
                 'select_intake_check_result'],
  'id': 'intake_check_terminal',
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

