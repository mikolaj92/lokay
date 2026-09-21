"""Independent conduction and when metadata for pr_triage_department."""
from __future__ import annotations

import json

_PATH_ID = 'pr_triage_department'
_NODES = {'list_pr_sieve': {'atom': 'list_pr_sieve', 'conduction': [], 'when': None},
 'reconcile_pr_repair_push': {'atom': 'reconcile_pr_repair_push',
                              'conduction': ['select_pr_sieve'],
                              'when': None},
 'recover_repair_closed_merged': {'atom': 'recover_repair_closed_merged',
                                  'conduction': ['reconcile_pr_repair_push'],
                                  'when': {'equals': 'closed_merged',
                                           'path': 'recovery_case',
                                           'upstream': 'reconcile_pr_repair_push'}},
 'recover_repair_confirmed_target': {'atom': 'recover_repair_confirmed_target',
                                     'conduction': ['reconcile_pr_repair_push'],
                                     'when': {'equals': 'confirmed_target',
                                              'path': 'recovery_case',
                                              'upstream': 'reconcile_pr_repair_push'}},
 'recover_repair_pre_attempt': {'atom': 'recover_repair_pre_attempt',
                                'conduction': ['reconcile_pr_repair_push'],
                                'when': {'equals': 'pre_attempt',
                                         'path': 'recovery_case',
                                         'upstream': 'reconcile_pr_repair_push'}},
 'recover_repair_remote_unchanged': {'atom': 'recover_repair_remote_unchanged',
                                     'conduction': ['reconcile_pr_repair_push'],
                                     'when': {'equals': 'remote_unchanged',
                                              'path': 'recovery_case',
                                              'upstream': 'reconcile_pr_repair_push'}},
 'recover_repair_unavailable': {'atom': 'recover_repair_unavailable',
                                'conduction': ['reconcile_pr_repair_push'],
                                'when': {'equals': 'unavailable',
                                         'path': 'recovery_case',
                                         'upstream': 'reconcile_pr_repair_push'}},
 'run_pr_sieve': {'atom': 'run_pr_sieve',
                  'conduction': ['reconcile_pr_repair_push'],
                  'when': {'equals': 'review',
                           'path': 'route',
                           'upstream': 'reconcile_pr_repair_push'}},
 'select_pr_sieve': {'atom': 'select_pr_sieve', 'conduction': ['list_pr_sieve'], 'when': None},
 'select_pr_triage_verdict': {'atom': 'select_pr_triage_verdict',
                              'conduction': ['select_pr_sieve',
                                             'reconcile_pr_repair_push',
                                             'run_pr_sieve',
                                             'recover_repair_pre_attempt',
                                             'recover_repair_remote_unchanged',
                                             'recover_repair_confirmed_target',
                                             'recover_repair_closed_merged',
                                             'recover_repair_unavailable'],
                              'when': None},
 'summarize_pr_triage_department': {'atom': 'summarize_pr_triage_department',
                                    'conduction': ['select_pr_sieve',
                                                   'reconcile_pr_repair_push',
                                                   'run_pr_sieve',
                                                   'select_pr_triage_verdict',
                                                   'recover_repair_pre_attempt',
                                                   'recover_repair_remote_unchanged',
                                                   'recover_repair_confirmed_target',
                                                   'recover_repair_closed_merged',
                                                   'recover_repair_unavailable'],
                                    'when': None}}
_COND_EDGES = [('list_pr_sieve', 'select_pr_sieve'),
 ('select_pr_sieve', 'reconcile_pr_repair_push'),
 ('reconcile_pr_repair_push', 'recover_repair_pre_attempt'),
 ('reconcile_pr_repair_push', 'recover_repair_remote_unchanged'),
 ('reconcile_pr_repair_push', 'recover_repair_confirmed_target'),
 ('reconcile_pr_repair_push', 'recover_repair_closed_merged'),
 ('reconcile_pr_repair_push', 'recover_repair_unavailable'),
 ('reconcile_pr_repair_push', 'run_pr_sieve'),
 ('select_pr_sieve', 'select_pr_triage_verdict'),
 ('reconcile_pr_repair_push', 'select_pr_triage_verdict'),
 ('run_pr_sieve', 'select_pr_triage_verdict'),
 ('recover_repair_pre_attempt', 'select_pr_triage_verdict'),
 ('recover_repair_remote_unchanged', 'select_pr_triage_verdict'),
 ('recover_repair_confirmed_target', 'select_pr_triage_verdict'),
 ('recover_repair_closed_merged', 'select_pr_triage_verdict'),
 ('recover_repair_unavailable', 'select_pr_triage_verdict'),
 ('select_pr_sieve', 'summarize_pr_triage_department'),
 ('reconcile_pr_repair_push', 'summarize_pr_triage_department'),
 ('run_pr_sieve', 'summarize_pr_triage_department'),
 ('select_pr_triage_verdict', 'summarize_pr_triage_department'),
 ('recover_repair_pre_attempt', 'summarize_pr_triage_department'),
 ('recover_repair_remote_unchanged', 'summarize_pr_triage_department'),
 ('recover_repair_confirmed_target', 'summarize_pr_triage_department'),
 ('recover_repair_closed_merged', 'summarize_pr_triage_department'),
 ('recover_repair_unavailable', 'summarize_pr_triage_department')]
_WHEN_BRANCHES = [('recover_repair_pre_attempt',
  {'equals': 'pre_attempt', 'path': 'recovery_case', 'upstream': 'reconcile_pr_repair_push'}),
 ('recover_repair_remote_unchanged',
  {'equals': 'remote_unchanged', 'path': 'recovery_case', 'upstream': 'reconcile_pr_repair_push'}),
 ('recover_repair_confirmed_target',
  {'equals': 'confirmed_target', 'path': 'recovery_case', 'upstream': 'reconcile_pr_repair_push'}),
 ('recover_repair_closed_merged',
  {'equals': 'closed_merged', 'path': 'recovery_case', 'upstream': 'reconcile_pr_repair_push'}),
 ('recover_repair_unavailable',
  {'equals': 'unavailable', 'path': 'recovery_case', 'upstream': 'reconcile_pr_repair_push'}),
 ('run_pr_sieve', {'equals': 'review', 'path': 'route', 'upstream': 'reconcile_pr_repair_push'})]
_EFFECTORS = [{'conduction': [], 'id': 'list_pr_sieve', 'when': None},
 {'conduction': ['list_pr_sieve'], 'id': 'select_pr_sieve', 'when': None},
 {'conduction': ['select_pr_sieve'], 'id': 'reconcile_pr_repair_push', 'when': None},
 {'conduction': ['reconcile_pr_repair_push'],
  'id': 'recover_repair_pre_attempt',
  'when': {'equals': 'pre_attempt',
           'path': 'recovery_case',
           'upstream': 'reconcile_pr_repair_push'}},
 {'conduction': ['reconcile_pr_repair_push'],
  'id': 'recover_repair_remote_unchanged',
  'when': {'equals': 'remote_unchanged',
           'path': 'recovery_case',
           'upstream': 'reconcile_pr_repair_push'}},
 {'conduction': ['reconcile_pr_repair_push'],
  'id': 'recover_repair_confirmed_target',
  'when': {'equals': 'confirmed_target',
           'path': 'recovery_case',
           'upstream': 'reconcile_pr_repair_push'}},
 {'conduction': ['reconcile_pr_repair_push'],
  'id': 'recover_repair_closed_merged',
  'when': {'equals': 'closed_merged',
           'path': 'recovery_case',
           'upstream': 'reconcile_pr_repair_push'}},
 {'conduction': ['reconcile_pr_repair_push'],
  'id': 'recover_repair_unavailable',
  'when': {'equals': 'unavailable',
           'path': 'recovery_case',
           'upstream': 'reconcile_pr_repair_push'}},
 {'conduction': ['reconcile_pr_repair_push'],
  'id': 'run_pr_sieve',
  'when': {'equals': 'review', 'path': 'route', 'upstream': 'reconcile_pr_repair_push'}},
 {'conduction': ['select_pr_sieve',
                 'reconcile_pr_repair_push',
                 'run_pr_sieve',
                 'recover_repair_pre_attempt',
                 'recover_repair_remote_unchanged',
                 'recover_repair_confirmed_target',
                 'recover_repair_closed_merged',
                 'recover_repair_unavailable'],
  'id': 'select_pr_triage_verdict',
  'when': None},
 {'conduction': ['select_pr_sieve',
                 'reconcile_pr_repair_push',
                 'run_pr_sieve',
                 'select_pr_triage_verdict',
                 'recover_repair_pre_attempt',
                 'recover_repair_remote_unchanged',
                 'recover_repair_confirmed_target',
                 'recover_repair_closed_merged',
                 'recover_repair_unavailable'],
  'id': 'summarize_pr_triage_department',
  'when': None}]


def test_every_conduction_edge_is_declared():
    got = {(str(up), nid) for nid, meta in _NODES.items() for up in meta['conduction']}
    assert got == set(_COND_EDGES)


def test_every_when_branch_is_declared():
    got = {(nid, json.dumps(meta['when'], sort_keys=True))
           for nid, meta in _NODES.items() if meta['when']}
    want = {(nid, json.dumps(when, sort_keys=True)) for nid, when in _WHEN_BRANCHES}
    assert got == want


def test_when_upstream_is_a_direct_parent():
    for nid, when in _WHEN_BRANCHES:
        assert when['upstream'] in _NODES[nid]['conduction']


def test_unconditional_nodes_succeed_without_outputs():
    from support.graph_model import run_model
    status = run_model(_EFFECTORS, {})
    for nid, meta in _NODES.items():
        if meta['when'] is None:
            assert status[nid] == 'succeeded'
