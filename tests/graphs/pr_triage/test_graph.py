"""Native Fala host_run_package proofs for pr_triage."""
from __future__ import annotations

import pytest

_PATH_ID = 'pr_triage'
_EFFECTORS = [{'conduction': [], 'id': 'pr_checks', 'when': None},
 {'conduction': ['pr_checks'], 'id': 'classify_pr_triage_checks', 'when': None},
 {'conduction': ['pr_checks', 'classify_pr_triage_checks'],
  'id': 'collect_pr_review_evidence',
  'when': {'equals': 'review', 'path': 'route', 'upstream': 'classify_pr_triage_checks'}},
 {'conduction': ['classify_pr_triage_checks', 'collect_pr_review_evidence'],
  'id': 'resolve_sha_review',
  'when': None},
 {'conduction': ['classify_pr_triage_checks', 'collect_pr_review_evidence', 'resolve_sha_review'],
  'id': 'pr_review_agent',
  'when': {'equals': 'agent', 'path': 'route', 'upstream': 'resolve_sha_review'}},
 {'conduction': ['classify_pr_triage_checks', 'resolve_sha_review', 'pr_review_agent'],
  'id': 'validate_pr_review',
  'when': None},
 {'conduction': ['collect_pr_review_evidence', 'validate_pr_review'],
  'id': 'pr_review_retry_agent',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_pr_review'}},
 {'conduction': ['validate_pr_review', 'pr_review_retry_agent'],
  'id': 'validate_pr_review_retry',
  'when': {'equals': 'retry', 'path': 'route', 'upstream': 'validate_pr_review'}},
 {'conduction': ['classify_pr_triage_checks',
                 'resolve_sha_review',
                 'validate_pr_review',
                 'validate_pr_review_retry'],
  'id': 'select_pr_review',
  'when': None},
 {'conduction': ['classify_pr_triage_checks', 'collect_pr_review_evidence', 'select_pr_review'],
  'id': 'review_evidence_catalog',
  'when': {'equals': 'evidence', 'path': 'route', 'upstream': 'select_pr_review'}},
 {'conduction': ['collect_pr_review_evidence', 'select_pr_review', 'review_evidence_catalog'],
  'id': 'evidence_review_agent',
  'when': {'equals': 'agent', 'path': 'route', 'upstream': 'review_evidence_catalog'}},
 {'conduction': ['select_pr_review', 'review_evidence_catalog', 'evidence_review_agent'],
  'id': 'validate_evidence_review',
  'when': {'equals': 'agent', 'path': 'route', 'upstream': 'review_evidence_catalog'}},
 {'conduction': ['classify_pr_triage_checks', 'select_pr_review', 'validate_evidence_review'],
  'id': 'select_evidence_review',
  'when': {'equals': 'review', 'path': 'route', 'upstream': 'classify_pr_triage_checks'}},
 {'conduction': ['classify_pr_triage_checks', 'select_pr_review', 'select_evidence_review'],
  'id': 'finalize_pr_review',
  'when': {'equals': 'review', 'path': 'route', 'upstream': 'classify_pr_triage_checks'}},
 {'conduction': ['classify_pr_triage_checks', 'collect_pr_review_evidence', 'finalize_pr_review'],
  'id': 'publish_pr_review',
  'when': None},
 {'conduction': ['classify_pr_triage_checks', 'publish_pr_review'], 'id': 'review_repair_gate', 'when': None},
 {'conduction': ['publish_pr_review', 'review_repair_gate'],
  'id': 'review_repair_manual',
  'when': {'equals': 'fail_closed', 'path': 'route', 'upstream': 'review_repair_gate'}},
 {'conduction': ['publish_pr_review'],
  'id': 'review_manual',
  'when': {'equals': 'fail_closed', 'path': 'decision.verdict', 'upstream': 'publish_pr_review'}},
 {'conduction': ['pr_checks', 'publish_pr_review'],
  'id': 'worktree_add',
  'when': {'equals': 'approve', 'path': 'decision.verdict', 'upstream': 'publish_pr_review'}},
 {'conduction': ['publish_pr_review', 'worktree_add'],
  'id': 'test_local',
  'when': {'equals': 'approve', 'path': 'decision.verdict', 'upstream': 'publish_pr_review'}},
 {'conduction': ['classify_pr_triage_checks', 'review_repair_gate', 'test_local'],
  'id': 'select_pr_triage_outcome',
  'when': None},
 {'conduction': ['classify_pr_triage_checks', 'select_pr_triage_outcome', 'publish_pr_review'],
  'id': 'pr_repair_verdict',
  'when': {'equals': 'repair', 'path': 'route', 'upstream': 'select_pr_triage_outcome'}},
 {'conduction': ['pr_checks', 'publish_pr_review', 'test_local', 'select_pr_triage_outcome'],
  'id': 'pr_merge',
  'when': {'equals': 'merge', 'path': 'route', 'upstream': 'select_pr_triage_outcome'}},
 {'conduction': ['publish_pr_review', 'pr_merge', 'select_pr_triage_outcome'],
  'id': 'stage_clear',
  'when': {'equals': 'merge', 'path': 'route', 'upstream': 'select_pr_triage_outcome'}},
 {'conduction': ['publish_pr_review', 'pr_merge', 'stage_clear', 'select_pr_triage_outcome'],
  'id': 'close_issue',
  'when': {'equals': 'merge', 'path': 'route', 'upstream': 'select_pr_triage_outcome'}},
 {'conduction': ['pr_merge', 'close_issue', 'select_pr_triage_outcome'],
  'id': 'publish_delivery_receipt',
  'when': {'equals': 'merge', 'path': 'route', 'upstream': 'select_pr_triage_outcome'}},
 {'conduction': ['classify_pr_triage_checks',
                 'select_pr_triage_outcome',
                 'pr_repair_verdict',
                 'review_repair_manual',
                 'review_manual',
                 'pr_merge',
                 'close_issue',
                 'publish_delivery_receipt',
                 'publish_pr_review'],
  'id': 'summarize_pr_triage',
  'when': None}]
_MATCH = {'classify_pr_triage_checks': {'route': 'review'},
 'publish_pr_review': {'decision': {'verdict': 'fail_closed'}, 'decision.verdict': 'fail_closed'},
 'resolve_sha_review': {'route': 'agent'},
 'review_evidence_catalog': {'route': 'agent'},
 'review_repair_gate': {'route': 'fail_closed'},
 'select_pr_review': {'route': 'evidence'},
 'select_pr_triage_outcome': {'route': 'repair'},
 'validate_pr_review': {'route': 'retry'}}
_MISS = {'classify_pr_triage_checks': {'route': 'not-review'},
 'publish_pr_review': {'decision': {'verdict': 'not-fail_closed'}, 'decision.verdict': 'not-fail_closed'},
 'resolve_sha_review': {'route': 'not-agent'},
 'review_evidence_catalog': {'route': 'not-agent'},
 'review_repair_gate': {'route': 'not-fail_closed'},
 'select_pr_review': {'route': 'not-evidence'},
 'select_pr_triage_outcome': {'route': 'not-repair'},
 'validate_pr_review': {'route': 'not-retry'}}
_MAX_TICKS = 108

def test_model_match_and_miss_differ_when_branches_exist():
    from support.graph_model import run_model
    matched = run_model(_EFFECTORS, _MATCH)
    missed = run_model(_EFFECTORS, _MISS)
    if _MATCH:
        assert matched != missed
    for item in _EFFECTORS:
        assert matched[item["id"]] in {"succeeded", "skipped"}
        assert missed[item["id"]] in {"succeeded", "skipped"}

def test_native_match_skips_nonmatching_adapters(tmp_path):
    from support.graph_model import node_status_map, run_model
    from support.native_path import run_overridden_path
    expected = run_model(_EFFECTORS, _MATCH)
    result = run_overridden_path(tmp_path, _PATH_ID, _MATCH, run_id="match", max_ticks=_MAX_TICKS)
    assert result.get("run_status") == "completed"
    native = node_status_map(result)
    assert native == expected
    ran = set(result.get("_ran") or [])
    for nid, status in native.items():
        if status == "skipped":
            assert nid not in ran
        elif status == "succeeded":
            assert nid in ran

def test_native_miss_skips_matching_when_branches(tmp_path):
    from support.graph_model import node_status_map, run_model
    from support.native_path import run_overridden_path
    if not _MISS:
        pytest.skip("path has no when branches")
    expected = run_model(_EFFECTORS, _MISS)
    result = run_overridden_path(tmp_path, _PATH_ID, _MISS, run_id="miss", max_ticks=_MAX_TICKS)
    assert result.get("run_status") == "completed"
    native = node_status_map(result)
    assert native == expected
    ran = set(result.get("_ran") or [])
    for nid, status in native.items():
        if status == "skipped":
            assert nid not in ran
