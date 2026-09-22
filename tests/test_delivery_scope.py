"""#1168 scope controls: repair authority, not #1169 replay or #1170 provenance."""
import tomllib
from pathlib import Path

from lokay.delivery_receipt import marker, parse_marker, verify_receipt
from lokay.proc.publish_delivery_receipt import publish


def test_unchanged_marker_keeps_baseline_provisional_provenance_policy():
    provisional = {
        'repo': 'o/r', 'issue': 42, 'work_id': 'o/r#42', 'head_sha': 'a' * 40,
        'graph_digest': 'pending', 'path_digest': 'issue_to_pr_delivery',
        'acceptance_digest': 'pending', 'builder_session': 'unavailable',
        'reviewer_session': 'pending', 'run_refs': [],
    }
    out = publish(
        repo='o/r', pr=57, issue=42, merge={'merged': True}, close={}, live=True,
        read_pr=lambda *_: {'body': marker(provisional), 'headRefOid': 'a' * 40,
                           'mergeCommit': {'oid': 'm'}, 'mergedAt': 't'},
        read_issue=lambda *_: {'state': 'CLOSED'}, main_contains=lambda *_: True,
        edit_pr=lambda *_: None,
    )
    assert out['confirmed'] is True
    completed = parse_marker(out['body'])
    assert completed is not None
    for key in ('graph_digest', 'path_digest', 'acceptance_digest',
                'builder_session', 'reviewer_session', 'run_refs'):
        assert completed[key] == provisional[key]
    assert verify_receipt(completed, observed_head='a' * 40, require_delivered=True)


def test_department_has_no_deferred_delivery_replay_nodes():
    root = Path(__file__).resolve().parents[1]
    for filename in ('fala/lokay.fala-package.toml', 'src/lokay/data/lokay.fala-package.toml'):
        package = tomllib.loads((root / filename).read_text())
        department = next(p for p in package['correlation_paths'] if p['id'] == 'pr_triage_department')
        assert not any('delivery_replay' in node['id'] for node in department['effectors'])
