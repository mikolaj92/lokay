"""PR-first at the native Fala producer/consumer boundary; no live effects."""

import json

import pytest
from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def pr_row(issue=1, *, labels=None, head=None):
    return {
        "number": 10, "title": "Existing work", "body": f"Fixes #{issue}",
        "headRefName": head or f"ai/fix/{issue}", "headRefOid": "a" * 40,
        "author": {"login": "bot"}, "url": "https://example.test/pr/10",
        "isDraft": False, "mergeable": "MERGEABLE",
        "labels": [] if labels is None else labels,
    }


def executor_graph(tmp_path, *, repo="o/r", rows=None, unavailable=False):
    body = base_effector(
        '''from unittest.mock import patch
from types import SimpleNamespace
from lokay.config import Config, RepoConfig
from lokay.organ.common import _conduction_values
from lokay.organ.issues_boundary import handle_issues
from lokay.organ.executor_department_boundary import handle_executor_department
up = _conduction_values(m)
cfg = Config(repos=[RepoConfig(name='o/r', clone_path=Path('/unused')),
                    RepoConfig(name='o/other', clone_path=Path('/unused'))])
inputs = {'live': True, 'listed': {'ok': True, 'issues': [
    {'repo': %r, 'issue': 2, 'labels': ['ai:ready']}]}}
def checked(self, spec, **kwargs):
    if %r:
        raise RuntimeError('survey unavailable')
    assert spec.argv[:3] == ('gh', 'pr', 'list'), spec.argv
    selected_repo = spec.argv[spec.argv.index('--repo') + 1]
    return SimpleNamespace(stdout=json.dumps(%r if selected_repo == 'o/r' else []))
with patch('lokay.config.load_config', return_value=cfg), \
     patch('lokay.config.department_enabled', return_value=True), \
     patch('lokay.runner.Runner.run_checked', checked), \
     patch('lokay.gh_prs.survey_pace'):
    if a == 'issues_launch_pr':
        v.update(route='started')
    else:
        result = handle_issues(a, inputs, up, {})
        if result is None:
            result = handle_executor_department(a, inputs, up, {})
        v.update(result)
Path(%r, a + '.json').write_text(json.dumps(v))
''' % (repo, unavailable, rows if rows is not None else [pr_row()], str(tmp_path))  # noqa: UP031 - embedded Python dict braces
    )
    return run_graph(tmp_path, body, "executor-pr-first", path_id="executor_row")


@pytest.mark.parametrize("repo,rows,unavailable,launch", [
    ("o/r", [pr_row()], False, False),
    ("o/other", [pr_row()], False, True),
    ("o/r", [pr_row(2)], False, True),
    ("o/r", [], True, False),
    ("o/r", [pr_row(2), pr_row(1)], False, False),
    ("o/r", [pr_row(labels=[{'name': 'ai:needs-review'}])], False, True),
    ("o/r", [pr_row(labels=[{'bogus': 'ai:needs-review'}])], False, False),
    ("o/r", [pr_row(head='feature/human')], False, True),
])
def test_native_executor_pr_first(tmp_path, repo, rows, unavailable, launch):
    result = executor_graph(tmp_path, repo=repo, rows=rows, unavailable=unavailable)
    gate = json.loads((tmp_path / 'select_issue_executor.json').read_text())
    assert gate['route'] == ('do' if launch else 'skip'), gate
    status = result['effector_results']['issues_launch_pr']['status']
    assert status == ('succeeded' if launch else 'skipped')
    assert gate['repo'] == repo and gate['issue'] == 2
    if not launch and not unavailable:
        blocker = gate['pr_admission']['blocking_prs'][0]
        assert (blocker['repo'], blocker['head_ref'], blocker['head_sha']) == (
            repo, 'ai/fix/1', 'a' * 40,
        )


@pytest.mark.parametrize("rows,unavailable,route", [
    ([pr_row()], False, 'no_effect'),
    ([], False, 'deliver'),
    ([pr_row(2)], False, 'closeout'),
    ([], True, 'no_effect'),
    ([pr_row(2), pr_row(1)], False, 'no_effect'),
])
def test_native_nested_delivery_pr_first(tmp_path, rows, unavailable, route):
    body = base_effector(
        '''from unittest.mock import patch
from types import SimpleNamespace
from lokay.config import Config, RepoConfig
from lokay.organ.common import _conduction_values
from lokay.organ.coding_boundary import handle_coding_boundary
up = _conduction_values(m)
cfg = Config(repos=[RepoConfig(name='o/r', clone_path=Path('/unused'))])
inputs = {'live': True}
ctx = {'repo': 'o/r', 'issue_number': 2}
rows = %r
def checked(self, spec, **kwargs):
    if %r:
        raise RuntimeError('survey unavailable')
    if spec.argv[:3] == ('gh', 'pr', 'list'):
        return SimpleNamespace(stdout=json.dumps(rows))
    assert spec.argv[:2] == ('gh', 'api'), spec.argv
    return SimpleNamespace(stdout=json.dumps([{
        'number': p['number'], 'body': p['body'], 'state': 'open',
        'head': {'ref': p['headRefName'], 'sha': p['headRefOid']}
    } for p in rows]))
with patch('lokay.organ.coding_boundary.load_config', return_value=cfg), \
     patch('lokay.runner.Runner.run_checked', checked), \
     patch('lokay.gh_prs.survey_pace'):
    if a == 'get_issue':
        v.update(issue={'number': 2, 'state': 'OPEN'})
    elif a == 'resolve_implementation_issue':
        v.update(route='open')
    elif a == 'collect_resumed_source':
        v.update(resumed_source=False)
    elif a in ('issue_to_pr_subflow', 'close_existing_delivery'):
        v.update(route='effect')
    else:
        v.update(handle_coding_boundary(a, inputs, up, ctx))
Path(%r, a + '.json').write_text(json.dumps(v))
''' % (rows, unavailable, str(tmp_path))  # noqa: UP031 - embedded Python dict braces
    )
    result = run_graph(tmp_path, body, 'nested-pr-first', path_id='issue_to_pr')
    resolved = json.loads((tmp_path / 'resolve_existing_delivery.json').read_text())
    assert resolved['route'] == route, resolved
    status = result['effector_results']['issue_to_pr_subflow']['status']
    assert status == ('succeeded' if route == 'deliver' else 'skipped')
    if route == 'no_effect':
        assert resolved['reason'] in ('actionable_pr', 'pr_survey_unavailable')


@pytest.mark.parametrize('unavailable', [False, True])
def test_launch_rechecks_after_acquiring_repo_lock(tmp_path, monkeypatch, unavailable):
    from types import SimpleNamespace

    from test_repo_lock import _parent_capability

    from lokay.config import Config, RepoConfig
    from lokay.proc.issue_delivery_launch import detach_issue_to_pr
    from lokay.proc.repo_lock import inspect_repo_lock, repo_lock_path

    _parent_capability(tmp_path, monkeypatch)
    cfg = Config(repos=[RepoConfig(name='o/r', clone_path=tmp_path)])
    monkeypatch.setattr('lokay.config.load_config', lambda *_: cfg)
    monkeypatch.setattr('lokay.gh_prs.survey_pace', lambda *_: None)
    lock = repo_lock_path(tmp_path / '.lokay', 'o/r')
    surveys = []
    spawned = []

    def checked(self, spec, **kwargs):
        assert spec.argv[:3] == ('gh', 'pr', 'list')
        busy = inspect_repo_lock(lock)['busy']
        surveys.append(busy)
        if not busy:
            return SimpleNamespace(stdout='[]')
        if unavailable:
            raise RuntimeError('PR survey unavailable')
        return SimpleNamespace(stdout=json.dumps([pr_row()]))

    def spawn(*args, **kwargs):
        spawned.append(True)
        return SimpleNamespace(pid=4242)

    monkeypatch.setattr('lokay.runner.Runner.run_checked', checked)
    from lokay.organ.issues_boundary import handle_issues

    monkeypatch.setattr('lokay.config.department_enabled', lambda *_: True)
    initial = handle_issues('select_issue_executor', {'live': True}, {
        'select_issue_do_row': {'route': 'do', 'repo': 'o/r', 'issue': 2},
    }, {})
    assert initial is not None and initial['route'] == 'do'
    result = detach_issue_to_pr(repo='o/r', issue=2, config_path=None, popen=spawn)
    assert result['ok'] is False, result
    assert result['reason'] == ('pr_survey_unavailable' if unavailable else 'actionable_pr')
    assert surveys == [False, True], 'launch must not trust the earlier clear survey'
    assert not spawned
    assert not inspect_repo_lock(lock)['busy'], 'denial must release the lock'
    assert not list((tmp_path / '.lokay').rglob('issue-to-pr-*.json'))


@pytest.mark.parametrize('stdout', ['', 'not-json', '{}', '[null]', '[{}]', 'cap'])
def test_unavailable_pr_list_fails_closed(tmp_path, monkeypatch, stdout):
    from types import SimpleNamespace

    from lokay.config import Config, RepoConfig
    from lokay.proc.inspect_repo_pr_admission import inspect
    from lokay.runner import Runner

    monkeypatch.setattr('lokay.gh_prs.survey_pace', lambda *_: None)
    monkeypatch.setattr('lokay.gh_prs.survey_list_cap', lambda: 2)
    if stdout == 'cap':
        stdout = json.dumps([pr_row(), pr_row()])
    monkeypatch.setattr('lokay.runner.Runner.run_checked',
                        lambda *_a, **_k: SimpleNamespace(stdout=stdout))
    cfg = Config(repos=[RepoConfig(name='o/r', clone_path=tmp_path)])
    result = inspect(runner=Runner(), config=cfg, repo='o/r', issue=2, live=True)
    assert result['allowed'] is False
    assert result['reason'] == 'pr_survey_unavailable'


def test_offline_admission_does_not_survey(tmp_path, monkeypatch):
    from lokay.config import Config
    from lokay.proc.inspect_repo_pr_admission import inspect
    from lokay.runner import Runner

    def forbidden(*args, **kwargs):
        raise AssertionError('offline must not call GitHub')

    monkeypatch.setattr('lokay.runner.Runner.run_checked', forbidden)
    result = inspect(runner=Runner(), config=Config(), repo='o/r', issue=2, live=False)
    assert result['allowed'] is False and result['planned'] is True


def test_nested_reducer_requires_authoritative_admission():
    from lokay.proc.resolve_existing_delivery import resolve

    assert resolve({'route': 'open'}, {}, {}) == {
        'ok': True, 'route': 'no_effect', 'reason': 'pr_survey_unavailable',
    }
