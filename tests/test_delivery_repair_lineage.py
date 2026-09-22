"""Verified repair checkpoint producer -> delivery marker consumer, with real Git/tests."""
import json
import sqlite3
from pathlib import Path

import pytest
from test_repair_checkpoint_producers import replace_output
from test_repair_publication_checkpoint import evidence, git

from lokay.delivery_receipt import marker, parse_marker
from lokay.proc import pr_repair_checkpoint as checkpoint
from lokay.proc import pr_repair_receipts as receipts
from lokay.proc.publish_delivery_receipt import publish


def produced(tmp_path, monkeypatch):
    from lokay.graph_run import run_path
    from lokay.proc import test_local_execution_subflow as tests
    inputs, outputs, ref, _ = evidence(tmp_path)
    work = Path(outputs['worktree_add']['worktree'])
    (work / 'pyproject.toml').write_text('[tool.lokay]\ntest = ["true"]\n')
    git(work, 'add', '.')
    git(work, 'commit', '-m', 'declared tests')
    target = git(work, 'rev-parse', 'HEAD')
    start = git(work, 'rev-parse', 'HEAD^')
    inputs['head_sha'] = inputs['reviewed_head_sha'] = start
    inputs['review']['reviewed_head_sha'] = start
    outputs['worktree_add'].update(repair_start_head_sha=start, worktree_head_sha=start)
    before = {'head': start, 'branch': inputs['branch'], 'origin': 'https://github.com/o/r.git'}
    outputs['run_agent']['revision'] = {'before': before, 'after': before}
    outputs['commit_initial_repair'].update(commit=target, revision={
        'before': before, 'after': {**before, 'head': target}, 'parents': [start]})
    with sqlite3.connect(ref['db']) as conn:
        conn.execute('UPDATE processes SET input_json=?', (json.dumps(inputs),))
    for name in ('worktree_add', 'run_agent', 'commit_initial_repair'):
        replace_output(ref, name, outputs[name])
    monkeypatch.setattr(tests, 'run_path', lambda **kw: run_path(**kw, db_path=tmp_path / 'native-tests'))
    tested = tests.run(worktree=str(work), changed_scope=False, repo='o/r', issue=42)
    assert tested['ok'] is True and tested['tested'] is True
    replace_output(ref, 'test_local', tested)
    assert checkpoint.persist(inputs=inputs, run_ref=ref, state_dir=tmp_path, budget=2)['route'] == 'checkpointed'
    proof = receipts.read('o/r', 57, state_dir=tmp_path)['publication_checkpoint']
    intent = proof['intent']
    receipts.prepare_push_intent(repo='o/r', pr=57, intent=intent, state_dir=tmp_path, budget=2)
    receipts.mark_push_attempted(repo='o/r', pr=57, intent_sha256=intent['intent_sha256'], state_dir=tmp_path)
    confirmed = receipts.confirm_pending_push(repo='o/r', pr=57, intent_sha256=intent['intent_sha256'],
        remote_head_sha=target, remote_branch=inputs['branch'], remote_repo='o/r', remote_state='OPEN', state_dir=tmp_path, budget=2)
    assert confirmed['route'] == 'confirmed'
    provisional = {'repo':'o/r', 'issue':42, 'work_id':'o/r#42', 'branch':inputs['branch'],
        'graph_digest':'sha256:' + '1'*64, 'path_digest':'sha256:' + '2'*64,
        'run_refs':[ref], 'builder_session':'builder-run-42', 'reviewer_session':'pending',
        'acceptance_digest':'sha256:' + '3'*64, 'head_sha':start,
        'acceptance_identity':'o/r#42', 'acceptance_accepted':True}
    review = {'ok':True, 'merge_ok':True, 'repo':'o/r', 'pr':57, 'head_sha':target,
              'decision': {'verdict':'approve', 'findings':[], 'reviewed_head_sha':target,
                           'task':inputs['task'], 'task_identity_sha256':inputs['task_identity_sha256'],
                           'review_result_sha256':'4'*64, 'review_evidence':{'run_id':'vendor-review-57'}}}
    return provisional, review, {**tested, 'tested_head_sha':target}, receipts.read('o/r', 57, state_dir=tmp_path)


@pytest.mark.parametrize('damage', [None, 'legacy_marker', 'missing_lineage', 'unrelated', 'repo', 'branch', 'task', 'work_id', 'unconfirmed', 'tamper', 'review', 'test', 'state', 'base'])
def test_authorized_repair_only_can_finalize_original_marker(tmp_path, monkeypatch, damage):
    provisional, review, test, repair = produced(tmp_path, monkeypatch)
    target = test['tested_head_sha']
    viewed = {'body':marker(provisional), 'headRefOid':target, 'headRefName':provisional['branch'],
              'headRepository':{'nameWithOwner':'o/r'}, 'baseRefName':'main',
              'mergeCommit':{'oid':target}, 'mergedAt':'2026-09-21T00:00:00Z', 'state':'MERGED'}
    if damage == 'unrelated':
        # Even a real, freshly tested/reviewed descendant is not recorded repair
        # authority: the confirmed checkpoint ends at the previous target.
        from lokay.proc.test_local_execution_subflow import run
        work = Path(test['worktree'])
        git(work, 'commit', '--allow-empty', '-m', 'unrelated change after authorized repair')
        unrelated = git(work, 'rev-parse', 'HEAD')
        test = {**run(worktree=str(work), changed_scope=False, repo='o/r', issue=42),
                'tested_head_sha': unrelated}
        review['head_sha'] = review['decision']['reviewed_head_sha'] = unrelated
        viewed['headRefOid'] = viewed['mergeCommit']['oid'] = unrelated
    if damage == 'repo': viewed['headRepository']['nameWithOwner'] = 'foreign/repo'
    if damage == 'branch': viewed['headRefName'] = 'ai/fix/99'
    if damage == 'task': provisional['issue'] = 99; viewed['body'] = marker(provisional)
    if damage == 'work_id': provisional['work_id'] = 'o/r#99'; viewed['body'] = marker(provisional)
    if damage == 'state': viewed['state'] = 'OPEN'
    if damage == 'base': viewed['baseRefName'] = 'release'
    if damage == 'legacy_marker':
        # Original markers predate the branch field; the recorded intent must
        # still bind the authoritative branch, not ancestry or a new marker.
        provisional.pop('branch')
        viewed['body'] = marker(provisional)
    if damage == 'missing_lineage': repair = {}
    if damage == 'unconfirmed': repair['checkpoint_terminal'] = ''
    if damage == 'tamper': repair['publication_checkpoint']['task']['number'] = 99
    if damage == 'review': review['decision']['reviewed_head_sha'] = provisional['head_sha']
    if damage == 'test': test['tested_head_sha'] = provisional['head_sha']
    edits = []
    out = publish(repo='o/r', pr=57, issue=42, merge={'merged':True}, close={}, live=True,
        read_pr=lambda *_: viewed, read_issue=lambda *_: {'state':'CLOSED'}, main_contains=lambda *_: True,
        edit_pr=lambda *args: edits.append(args), repair_receipt=repair, review=review, tests=test)
    authorized = damage in (None, 'legacy_marker')
    assert out['confirmed'] is authorized, out
    assert bool(edits) is authorized
    if damage == 'unrelated':
        assert test['tested'] is True
        assert out['reason'] == 'receipt_identity_mismatch'
    if authorized:
        completed = parse_marker(out['body'])
        assert completed is not None
        assert completed['head_sha'] == target
        assert completed['original_head_sha'] == provisional['head_sha']
        assert completed['repair_lineage'][0]['checkpoint_sha256'] == repair['publication_checkpoint']['sha256']
        assert completed['reviewed_head_sha'] == completed['tested_head_sha'] == target
        assert completed['reviewer_session'] == review['decision']['review_evidence']['run_id']
        assert completed['issue_closed'] is True
