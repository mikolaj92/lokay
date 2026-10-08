from lokay.proc.launch_issue_to_pr import launch


def test_cap_blocks_a_second_launch():
    out = launch({'repo': 'o/r', 'issue': 1}, config_path=None, live=True, merge_ready=1, merge_ready_cap=1)
    assert out['route'] == 'busy'
    assert out['reason'] == 'merge_ready_cap'


def test_cap_zero_does_not_block(monkeypatch):
    monkeypatch.setattr('lokay.proc.launch_issue_to_pr.detach_issue_to_pr', lambda **kw: {'ok': True})
    out = launch({'repo': 'o/r', 'issue': 1, 'leftover_issues': []}, config_path=None, live=True, live_count=0, merge_ready=3, merge_ready_cap=0)
    assert out['route'] == 'started'
