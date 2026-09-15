"""Native Fala host_run_package proofs for pr_triage_department."""
from __future__ import annotations

import pytest

_PATH_ID = 'pr_triage_department'
_EFFECTORS = [
    {'conduction': [], 'id': 'list_pr_sieve', 'when': None},
    {'conduction': ['list_pr_sieve'], 'id': 'select_pr_sieve', 'when': None},
    {'conduction': ['select_pr_sieve'], 'id': 'reconcile_pr_repair_push', 'when': None},
    {'conduction': ['reconcile_pr_repair_push'], 'id': 'run_pr_sieve',
     'when': {'equals': 'review', 'path': 'route', 'upstream': 'reconcile_pr_repair_push'}},
    {'conduction': ['select_pr_sieve', 'reconcile_pr_repair_push', 'run_pr_sieve'],
     'id': 'select_pr_triage_verdict', 'when': None},
    {'conduction': ['select_pr_sieve', 'reconcile_pr_repair_push', 'run_pr_sieve',
                    'select_pr_triage_verdict'],
     'id': 'summarize_pr_triage_department', 'when': None},
]
_MATCH = {
    'select_pr_sieve': {'route': 'pr'},
    'reconcile_pr_repair_push': {'route': 'review'},
}
_RECOVERED = {
    'select_pr_sieve': {'route': 'pr'},
    'reconcile_pr_repair_push': {'route': 'recovered'},
}
_FAILED = {
    'select_pr_sieve': {'route': 'pr'},
    'reconcile_pr_repair_push': {'route': 'fail_closed'},
}
_NO_PR = {
    'select_pr_sieve': {'route': 'none'},
    'reconcile_pr_repair_push': {'route': 'no_pr'},
}
_LIST_FAILED = {
    'select_pr_sieve': {'route': 'none', 'reason': 'list_failed'},
    'reconcile_pr_repair_push': {'route': 'no_pr'},
}
_MAX_TICKS = 40


def test_model_match_and_miss_differ_when_branches_exist():
    from support.graph_model import run_model
    matched = run_model(_EFFECTORS, _MATCH)
    recovered = run_model(_EFFECTORS, _RECOVERED)
    assert matched != recovered
    for item in _EFFECTORS:
        assert matched[item['id']] in {'succeeded', 'skipped'}
        assert recovered[item['id']] in {'succeeded', 'skipped'}


def test_native_match_skips_nonmatching_adapters(tmp_path):
    from support.graph_model import node_status_map, run_model
    from support.native_path import run_overridden_path
    expected = run_model(_EFFECTORS, _MATCH)
    result = run_overridden_path(tmp_path, _PATH_ID, _MATCH, run_id='match', max_ticks=_MAX_TICKS)
    assert result.get('run_status') == 'completed'
    native = node_status_map(result)
    assert native == expected
    assert native['reconcile_pr_repair_push'] == 'succeeded'
    ran = set(result.get('_ran') or [])
    for nid, status in native.items():
        if status == 'skipped':
            assert nid not in ran
        elif status == 'succeeded':
            assert nid in ran


def test_native_recovery_route_skips_review(tmp_path):
    from support.graph_model import node_status_map, run_model
    from support.native_path import run_overridden_path
    for values, run_id in ((_RECOVERED, 'recovered'), (_FAILED, 'failed')):
        expected = run_model(_EFFECTORS, values)
        result = run_overridden_path(
            tmp_path, _PATH_ID, values, run_id=run_id, max_ticks=_MAX_TICKS,
        )
        assert result.get('run_status') == 'completed'
        native = node_status_map(result)
        assert native == expected
        assert native['reconcile_pr_repair_push'] == 'succeeded'
        assert native['run_pr_sieve'] == 'skipped'
        ran = set(result.get('_ran') or [])
        assert 'run_pr_sieve' not in ran
        assert 'select_pr_triage_verdict' in ran


def test_native_no_pr_and_failed_listing_both_skip_review(tmp_path):
    from support.graph_model import node_status_map, run_model
    from support.native_path import run_overridden_path
    for values, run_id in ((_NO_PR, 'no-pr'), (_LIST_FAILED, 'list-failed')):
        expected = run_model(_EFFECTORS, values)
        result = run_overridden_path(
            tmp_path, _PATH_ID, values, run_id=run_id, max_ticks=_MAX_TICKS,
        )
        assert result.get('run_status') == 'completed'
        native = node_status_map(result)
        assert native == expected
        assert native['reconcile_pr_repair_push'] == 'succeeded'
        assert native['run_pr_sieve'] == 'skipped'
        assert 'run_pr_sieve' not in result.get('_ran', [])
        assert 'select_pr_triage_verdict' in result.get('_ran', [])


def test_native_fail_closed_route_suppresses_review(tmp_path):
    from support.graph_model import node_status_map, run_model
    from support.native_path import run_overridden_path
    expected = run_model(_EFFECTORS, _FAILED)
    result = run_overridden_path(
        tmp_path, _PATH_ID, _FAILED, run_id='fail-closed', max_ticks=_MAX_TICKS,
    )
    assert result.get('run_status') == 'completed'
    assert node_status_map(result) == expected
    assert node_status_map(result)['reconcile_pr_repair_push'] == 'succeeded'
    assert node_status_map(result)['run_pr_sieve'] == 'skipped'
    assert 'run_pr_sieve' not in result.get('_ran', [])
