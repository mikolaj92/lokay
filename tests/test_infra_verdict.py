from lokay.proc.run_pr_review_agent import infra_verdict


def test_named_infra_code_becomes_a_verdict():
    assert infra_verdict('tools_allowlist_invalid: missing tool') == {'verdict': 'infra_failure', 'reason': 'tools_allowlist_invalid'}


def test_product_failure_stays_unclassified():
    assert infra_verdict('review result invalid') is None
