"""A PR-first refusal preserves the issue, but cannot pin every executor slot."""

from lokay.config import Config
from lokay.organ.issues_boundary import handle_issues
from lokay.proc.classify_executor_row import classify
from lokay.proc.select_issue_do_row import select as select_do
from lokay.proc.select_next_issue import select as pick
from lokay.proc.summarize_executor_row import summarize


def test_blocked_candidate_advances_without_launch_budget_or_queue_request(tmp_path, monkeypatch):
    cfg = Config(mode='live', executor_enabled=True)
    listed = {'issues': [
        {'repo': 'o/busy', 'issue': 23, 'labels': ['ai:ready']},
        {'repo': 'o/free', 'issue': 7, 'labels': ['ai:ready']},
    ]}
    monkeypatch.setattr('lokay.config.load_config', lambda *_: cfg)
    monkeypatch.setattr('lokay.config.department_enabled', lambda *_: True)
    surveys, queue_calls = [], []

    def admission(**kwargs):
        surveys.append((kwargs['repo'], kwargs['issue']))
        return {'allowed': kwargs['repo'] == 'o/free',
                'reason': 'actionable_pr' if kwargs['repo'] == 'o/busy' else 'pr_first_clear',
                'blocking_prs': [{'repo': 'o/busy', 'pr': 28, 'head_sha': 'a' * 40}]}

    def queue(**kwargs):
        queue_calls.append(kwargs['selected']['repo'])
        return kwargs['selected']

    monkeypatch.setattr('lokay.proc.inspect_repo_pr_admission.inspect', admission)
    monkeypatch.setattr('lokay.proc.check_executor_queue.check', queue)
    last = {}
    chosen = pick(listed, last, occupied=set())
    gate = handle_issues('select_issue_executor', {'live': True, 'listed': listed},
                        {'select_issue_do_row': select_do(chosen, listed)}, {})
    assert gate['route'] == 'skip' and gate['reason'] == 'actionable_pr'
    assert queue_calls == []
    row = summarize(chosen, gate, {})
    classified = classify({'route': 'run', 'slot': 1}, row,
                          prepared={'spent': 0, 'cap': 1, 'pass_dir': str(tmp_path)})
    assert classified['spent'] == 0
    # Actual producer -> receipt -> next selector, not a locally rewritten queue.
    next_chosen = pick(listed, classified['result'], occupied=set())
    assert (next_chosen['repo'], next_chosen['issue']) == ('o/free', 7)
    next_gate = handle_issues('select_issue_executor', {'live': True, 'listed': listed},
                             {'select_issue_do_row': select_do(next_chosen, listed)}, {})
    assert next_gate['route'] == 'do'
    assert queue_calls == ['o/free']
    assert surveys == [('o/busy', 23), ('o/free', 7)]
    # No source mutation: the blocked work remains ready in the next fresh listing.
    assert listed['issues'][0]['labels'] == ['ai:ready']
    assert pick(listed, {}, occupied=set())['issue'] == 23
