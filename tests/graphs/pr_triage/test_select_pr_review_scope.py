"""Independent contract for the deterministic review-scope node."""
_PATH_ID = 'pr_triage'
_NODE_ID = 'select_pr_review_scope'
_ATOM = 'select_pr_review_scope'
_CONDUCTION = ['classify_pr_triage_checks', 'collect_pr_review_evidence', 'resolve_sha_review']
_WHEN = {'equals': 'agent', 'path': 'route', 'upstream': 'resolve_sha_review'}
_REQUIRED_WHEN_FIELDS = ['route']


def test_scope_failure_is_classified_without_starting_review():
    from lokay.organ.review_boundary import handle_review_boundary
    result = handle_review_boundary('validate_pr_review', {}, {
        'resolve_sha_review': {'route': 'agent'},
        'select_pr_review_scope': {'route': 'fail_closed', 'reason': 'ocr_scope_incomplete'},
    }, {'repo': 'a/b', 'pr_number': 7, 'branch': '', 'live': True})
    assert result == {'ok': True, 'route': 'fail_closed', 'reason': 'ocr_scope_incomplete'}
