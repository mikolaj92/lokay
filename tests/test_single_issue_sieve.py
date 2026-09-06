"""A published triage decision is not input to a second intake engine (#1031)."""

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
    ('park', 'shape_uncertain', 'park'),
    ('park', 'issue_split', 'split'),
    ('needs_human', 'czlowiek', 'park'),
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
    assert not any(e['id'] == 'run_issue_sieve_intake' for e in row['effectors'])


def test_issue_triage_prompt_has_zero_needs_human():
    text = (ROOT / 'src/lokay/tool_contracts/issue_triage/prompt.md').read_text()
    low = text.lower()
    assert "needs_human" not in low
    assert "człowiek" not in text and "czlowiek" not in low
    assert "park" in low
    assert "never ask for a person" in low or "zero human" in low or "never invent a human" in low

    assert 'fail-closed' in text.lower() or 'fail closed' in text.lower() or 'park' in text


def test_issue_triage_schema_excludes_needs_human():
    from lokay.issue_triage_agent import SCHEMA
    from lokay.issue_triage_boundary import VERDICTS

    assert 'needs_human' not in SCHEMA
    assert 'needs_human' not in VERDICTS
    assert VERDICTS == frozenset({'ready', 'close', 'needs_evidence', 'park'})
