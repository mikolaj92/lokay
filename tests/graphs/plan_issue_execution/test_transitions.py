"""Independent conduction and when metadata for plan_issue_execution."""
from __future__ import annotations
import json

_PATH_ID = 'plan_issue_execution'
_NODES = {'authorize_issue_plan_write': {'atom': 'authorize_issue_plan_write',
                                'conduction': ['prepare_issue_plan_request', 'build_issue_approach'],
                                'when': None},
 'build_issue_approach': {'atom': 'build_issue_approach',
                          'conduction': ['prepare_issue_plan_request'],
                          'when': None},
 'issue_plan_terminal': {'atom': 'issue_plan_terminal',
                         'conduction': ['prepare_issue_plan_request',
                                        'build_issue_approach',
                                        'authorize_issue_plan_write',
                                        'record_issue_approach_write'],
                         'when': None},
 'prepare_issue_plan_request': {'atom': 'prepare_issue_plan_request', 'conduction': [], 'when': None},
 'record_issue_approach_write': {'atom': 'record_issue_approach_write',
                                 'conduction': ['authorize_issue_plan_write', 'write_issue_approach'],
                                 'when': None},
 'write_issue_approach': {'atom': 'write_issue_approach',
                          'conduction': ['prepare_issue_plan_request',
                                         'build_issue_approach',
                                         'authorize_issue_plan_write'],
                          'when': {'equals': 'write',
                                   'path': 'route',
                                   'upstream': 'authorize_issue_plan_write'}}}
_COND_EDGES = [('prepare_issue_plan_request', 'build_issue_approach'),
 ('prepare_issue_plan_request', 'authorize_issue_plan_write'),
 ('build_issue_approach', 'authorize_issue_plan_write'),
 ('prepare_issue_plan_request', 'write_issue_approach'),
 ('build_issue_approach', 'write_issue_approach'),
 ('authorize_issue_plan_write', 'write_issue_approach'),
 ('authorize_issue_plan_write', 'record_issue_approach_write'),
 ('write_issue_approach', 'record_issue_approach_write'),
 ('prepare_issue_plan_request', 'issue_plan_terminal'),
 ('build_issue_approach', 'issue_plan_terminal'),
 ('authorize_issue_plan_write', 'issue_plan_terminal'),
 ('record_issue_approach_write', 'issue_plan_terminal')]
_WHEN_BRANCHES = [('write_issue_approach', {'equals': 'write', 'path': 'route', 'upstream': 'authorize_issue_plan_write'})]
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

def test_every_conduction_edge_is_declared():
    got = {(str(up), nid) for nid, meta in _NODES.items() for up in meta["conduction"]}
    assert got == set(tuple(edge) for edge in _COND_EDGES)

def test_every_when_branch_is_declared():
    got = {(nid, json.dumps(meta["when"], sort_keys=True)) for nid, meta in _NODES.items() if meta["when"]}
    want = {(nid, json.dumps(when, sort_keys=True)) for nid, when in _WHEN_BRANCHES}
    assert got == want

def test_when_upstream_is_a_direct_parent():
    for nid, when in _WHEN_BRANCHES:
        assert when["upstream"] in _NODES[nid]["conduction"]

def test_unconditional_nodes_succeed_without_outputs():
    from support.graph_model import run_model
    status = run_model(_EFFECTORS, {})
    for nid, meta in _NODES.items():
        if meta["when"] is None:
            assert status[nid] == "succeeded"

