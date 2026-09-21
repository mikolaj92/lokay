"""C6: durable repair-intent producer -> native PR-sieve consumer."""

import pytest
from test_issue_triage_fala import base_effector, run_graph

from lokay.proc import pr_repair_receipts as receipts


def test_malformed_unrelated_receipt_cannot_block_selected_pr(tmp_path, monkeypatch):
    from lokay.proc.reconcile_pr_repair_push import reconcile_pending
    path = receipts.receipt_path('stale/repo', 1, state_dir=tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text('not json')
    monkeypatch.setattr(receipts, 'resolve_state_dir', lambda cfg: tmp_path)
    selected = {'ok': True, 'route': 'pr', 'repo': 'o/r', 'pr': 9, 'branch': 'ai/fix/9'}
    assert reconcile_pending(config_path=None, live=False, selection=selected)['route'] == 'review'
    selected.update(repo='stale/repo', pr=1)
    assert reconcile_pending(config_path=None, live=False, selection=selected)['reason'] == 'pr_repair_receipt_invalid'
    assert path.read_text() == 'not json'


def test_unavailable_recovery_keeps_identity_at_tail_not_global_head():
    from lokay.proc.summarize_pr_triage_department import summarize
    picked = {'ok': True, 'route': 'pr', 'repo': 'o/r', 'pr': 9, 'branch': 'ai/fix/9', 'head_sha': 'a' * 40,
                  'leftover_prs': [{'repo': 'other/repo', 'pr': 1, 'head_sha': 'b' * 40}]}
    result = summarize(picked, {}, {}, {'route': 'fail_closed', 'recovery_case': 'unavailable',
                       'reason': 'repair_push_remote_identity_unavailable'}, incomplete_retry_position='tail')
    assert result['leftover_prs'][0]['repo'] == 'other/repo'
    assert result['leftover_prs'][-1]['head_sha'] == 'a' * 40
    assert 'skipped_pr' not in result


@pytest.mark.parametrize('case', ['pre_attempt', 'remote_unchanged', 'confirmed_target', 'closed_merged', 'unavailable'])
def test_authored_named_recovery_transitions(tmp_path, case):
    marker = tmp_path / 'case'
    body = base_effector(f'''
if a == 'list_pr_sieve': v.update(prs=[])
elif a == 'select_pr_sieve': v.update(route='pr', repo='o/r', pr=9, branch='ai/fix/9')
elif a == 'reconcile_pr_repair_push': v.update(route='fail_closed', recovery_case={case!r})
elif a.startswith('recover_repair_'):
    Path({str(marker)!r}).write_text(a)
    v.update(route='fail_closed', reason='test_terminal')
elif a == 'run_pr_sieve': raise AssertionError('recovery must not review')
''')
    result = run_graph(tmp_path, body, 'case-' + case, 'pr_triage_department')
    assert result['ok'] is True, result
    assert marker.exists(), result
    assert marker.read_text() == 'recover_repair_' + case


@pytest.mark.parametrize("attempted", [False, True])
@pytest.mark.parametrize("repo,pr", [
    ("stale/repo", 1), ("stale/repo", 9), ("other/repo", 1), ("other/repo", 9),
])
def test_pending_repair_blocks_only_its_own_pr(tmp_path, attempted, repo, pr):
    related = (repo, pr) == ("stale/repo", 1)
    branch = f"ai/fix/{pr}"
    config = tmp_path / "config.yaml"
    config.write_text(f"state:\n  path: {tmp_path / 'state.jsonl'}\n")
    intent = receipts.build_push_intent(
        repo="stale/repo", pr=1, branch="ai/fix/1", repair_kind="ci",
        start_head_sha="a" * 40, target_head_sha="b" * 40,
    )
    assert receipts.prepare_push_intent(
        repo="stale/repo", pr=1, intent=intent, state_dir=tmp_path,
    )["route"] == "recorded"
    if attempted:
        assert receipts.mark_push_attempted(
            repo="stale/repo", pr=1, intent_sha256=intent["intent_sha256"],
            state_dir=tmp_path,
        )["route"] == "ready"
    before = receipts.receipt_path("stale/repo", 1, state_dir=tmp_path).read_bytes()
    review_marker = tmp_path / "reviewed"
    selected = {
        "ok": True, "route": "pr", "repo": repo, "pr": pr,
        "branch": branch, "head_sha": "a" * 40,
    }
    body = base_effector(f'''
from lokay.organ.common import _conduction_values
from lokay.organ.pr_triage_department_boundary import handle_pr_triage_department
from lokay.proc import probe_pr_state
# Only remote observation and review effects are replaced. Intent storage,
# reconciliation, native conduction, verdict and summary remain production code.
probe_pr_state.probe = lambda **kw: {{
    'ok': True, 'route': 'open', 'state': 'OPEN', 'head_repo': kw['repo'],
    'head_ref': 'ai/fix/1', 'head_ref_sha': {'a' * 40!r},
}}
if a == 'list_pr_sieve': v.update(prs=[])
elif a == 'select_pr_sieve': v = {selected!r}
elif a == 'run_pr_sieve':
    Path({str(review_marker)!r}).write_text({repo!r})
    v.update(route='completed', triage={{'waiting': True, 'reason': 'test_review_wait'}})
else:
    v = handle_pr_triage_department(a,
        {{'config_path': {str(config)!r}, 'live': True}}, _conduction_values(m), {{}})
''')
    result = run_graph(tmp_path, body, f"isolation-{attempted}-{related}", "pr_triage_department")
    assert result["ok"] is True, result
    assert review_marker.exists() is (not related), result
    # Neither uncertainty nor unrelated review counts as a confirmed repair.
    stored = receipts.read("stale/repo", 1, state_dir=tmp_path)
    assert stored["attempts"] == 0
    assert stored["pending_push"]["intent_sha256"] == intent["intent_sha256"]
    assert receipts.receipt_path("stale/repo", 1, state_dir=tmp_path).read_bytes() == before
