"""A published triage decision is not input to a second intake engine."""

import tomllib
from pathlib import Path

import pytest
from lokay.proc.select_issue_sieve import classify_sieve

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(('verdict', 'reason', 'route'), [
    ('close', 'superseded', 'park'),
    ('close', 'superseded_oversized_split', 'park'),
    ('blocked', 'duplicate_pr_split', 'park'),
    ('ready', 'shape_verified_split', 'do'),
    ('blocked', 'duplicate_pr', 'park'),
    ('ready', 'shape_verified', 'do'),
    ('skip', 'intake_superseded', 'skip'),
    ('needs_human', 'shape_uncertain', 'human'),
])
def test_terminal_verdict_is_not_rerouted_by_intake_words(verdict, reason, route):
    out = classify_sieve({'triage': {'decision': {'verdict': verdict, 'reason': reason}}}, {})
    assert out['route'] == route


def test_sieve_has_no_second_intake_node_or_receipt_dependency():
    pkg = tomllib.loads((ROOT / 'fala/lokay.fala-package.toml').read_text())
    row = next(p for p in pkg['correlation_paths'] if p['id'] == 'issue_sieve_row')
    assert all('intake' not in e['id'] for e in row['effectors'])
    receipt = next(e for e in row['effectors'] if e['id'] == 'summarize_issue_sieve_row')
    assert 'run_issue_sieve_intake' not in receipt['conduction']
