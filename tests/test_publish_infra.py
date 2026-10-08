from lokay.proc.publish_pr_review import publish


def test_infra_route_is_not_published_as_fail_closed():
    out = publish(cfg=None, repo='o/r', pr=1, evidence={'head_sha': 'a'*40}, selected={'route': 'infra', 'reason': 'tools_allowlist_invalid'}, live=False)
    assert out['decision']['verdict'] == 'infra_failure'
    assert out['applied'] is False
