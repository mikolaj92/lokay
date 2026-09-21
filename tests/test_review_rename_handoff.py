"""#1157: real neutral adapter -> independent host for rename findings."""
import hashlib
import json

import pytest

from test_pr_review_validation import FIXTURES, _request
from lokay.proc.validate_pr_review import validate_result
from lokay_review_open_code_review.contract import normalize_result


def renamed_review(*, findings=True):
    request = _request()
    request['diff_paths'] = [
        {'path': 'src/demo.py', 'old_path': 'src/old.py', 'status': 'renamed'},
        {'path': 'src/other.py', 'old_path': '', 'status': 'modified'},
        {'path': 'src/deleted.py', 'old_path': '', 'status': 'deleted'},
    ]
    upstream = json.loads((FIXTURES / 'review-complete.json').read_text())
    upstream['manifest']['repository']['identity_sha256'] = hashlib.sha256(b'github.com/acme/demo').hexdigest()
    coverage = upstream['manifest']['coverage']
    for key in ('selected', 'completed'):
        coverage[key] = [{'path': row['path'], 'old_path': row['old_path']}
                         for row in request['diff_paths'] if row['status'] != 'deleted']
    if not findings:
        upstream['comments'] = []
    result = normalize_result(request, upstream, engine={
        'name': 'open-code-review', 'version': 'v1.12.7', 'binary_sha256': 'f' * 64,
        'provider': 'example-provider', 'model': 'example-model', 'config_sha256': '9' * 64,
    }, changed_ranges=request['changed_ranges'])
    return request, result


@pytest.mark.parametrize('findings,verdict', [(True, 'request_changes'), (False, 'approve')])
def test_plugin_to_host_accepts_exact_rename_identity(findings, verdict):
    request, result = renamed_review(findings=findings)
    validated = validate_result(result, request)
    assert validated['route'] == 'valid', validated
    assert validated['decision']['verdict'] == verdict


@pytest.mark.parametrize('drift', ['old_name_anchor', 'outside_hunk', 'coverage_old_name'])
def test_rename_does_not_relax_anchor_or_identity(drift):
    request, result = renamed_review()
    if drift == 'old_name_anchor':
        result['findings'][0]['path'] = 'src/old.py'
    elif drift == 'outside_hunk':
        result['findings'][0].update(start_line=99, end_line=99)
    else:
        result['coverage']['reviewable_paths'][0]['old_path'] = 'src/wrong.py'
    assert validate_result(result, request)['route'] == 'fail_closed'
