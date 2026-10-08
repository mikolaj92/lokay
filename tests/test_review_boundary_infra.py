from lokay.organ.review_boundary import handle_review_boundary


def test_infra_agent_result_stays_infra(monkeypatch):
    monkeypatch.setattr('lokay.proc.run_pr_review_agent.run_review_agent', lambda **kw: {'ok': False, 'route': 'infra', 'reason': 'tools_allowlist_invalid', 'decision': {'verdict': 'infra_failure'}})
    out = handle_review_boundary('pr_review_agent', {}, {'resolve_sha_review': {'route': 'agent'}}, {'repo': 'o/r', 'pr_number': 1, 'branch': 'ai/fix/1', 'live': False})
    assert out['route'] == 'infra'
    assert out['reason'] == 'tools_allowlist_invalid'

def test_validate_names_an_infra_plugin_error():
    out = handle_review_boundary('validate_pr_review', {}, {'pr_review_agent': {'plugin_error': 'tools_allowlist_invalid: missing tool'}, 'select_pr_review_scope': {}}, {'repo': 'o/r', 'pr_number': 1, 'branch': 'ai/fix/1', 'live': False})
    assert out['route'] == 'infra'
    assert out['reason'] == 'tools_allowlist_invalid'
