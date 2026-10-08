from lokay.organ.lanes import handle_lanes


def test_disabled_approved_pr_gets_merge_ready(monkeypatch):
    seen = []
    monkeypatch.setattr('lokay.config.load_config', lambda *_: type('C', (), {'merge_mode': 'off', 'require_checks': False})())
    monkeypatch.setattr('lokay.proc.pr_label.main', lambda argv: seen.append(argv) or 0)
    review = {'decision': {'merge_ok': True, 'verdict': 'approve'}}
    out = handle_lanes('pr_merge', {'live': False}, {'publish_pr_review': review, 'pr_checks': {}}, {'cfg': [], 'live': [], 'repo': 'o/r', 'pr_number': 7, 'issue_number': 7, 'branch': 'ai/fix/7'})
    assert out['reason'] == 'merge_disabled'
    assert out['labels'] == ['ai:merge-ready']
    assert seen and seen[0][-1] == 'ai:merge-ready'


def test_disabled_unapproved_pr_gets_no_label(monkeypatch):
    monkeypatch.setattr('lokay.config.load_config', lambda *_: type('C', (), {'merge_mode': 'off', 'require_checks': False})())
    out = handle_lanes('pr_merge', {'live': False}, {'publish_pr_review': {'decision': {'merge_ok': False}}, 'pr_checks': {}}, {'cfg': [], 'live': [], 'repo': 'o/r', 'pr_number': 7, 'issue_number': 7, 'branch': 'ai/fix/7'})
    assert out['labels'] == []
